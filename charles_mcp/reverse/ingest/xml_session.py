"""XML session ingestion for official Charles XML exports."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path

from defusedxml import ElementTree as ET

from charles_mcp.reverse.ingest.common import (
    build_body_blob_id,
    hash_headers,
    header_value,
    parse_cookie_header,
    parse_set_cookie_headers,
    reason_phrase,
)
from charles_mcp.reverse.models import (
    BodyBlob,
    BodyPreservationLevel,
    BodyStorageKind,
    Capture,
    CaptureSourceFormat,
    CaptureSourceKind,
    Entry,
    Request,
    Response,
)


@dataclass
class ImportedEntryGraph:
    entry: Entry
    request: Request
    response: Response
    body_blobs: list[BodyBlob]


@dataclass
class ImportedCaptureGraph:
    capture: Capture
    entries: list[ImportedEntryGraph]
    warnings: list[str]


def parse_charles_xml_session(
    path: str | Path,
    *,
    capture_id: str,
    source_kind: CaptureSourceKind,
) -> ImportedCaptureGraph:
    """Parse an official Charles XML export into canonical entities."""
    xml_path = Path(path)
    tree = ET.parse(xml_path)
    root = tree.getroot()
    if root.tag != "charles-session":
        raise ValueError(f"Unsupported Charles XML root: {root.tag}")

    graphs: list[ImportedEntryGraph] = []
    warnings: list[str] = []

    for sequence_no, txn in enumerate(root.findall("transaction"), start=1):
        graphs.append(_parse_transaction(txn, capture_id=capture_id, sequence_no=sequence_no))

    capture = Capture(
        capture_id=capture_id,
        source_kind=source_kind,
        source_format=CaptureSourceFormat.XML,
        ingest_status="ready",
        entry_count=len(graphs),
        metadata={"source_path": str(xml_path)},
    )
    return ImportedCaptureGraph(capture=capture, entries=graphs, warnings=warnings)


def _parse_transaction(
    txn: ET.Element,
    *,
    capture_id: str,
    sequence_no: int,
) -> ImportedEntryGraph:
    method = txn.attrib.get("method", "GET")
    protocol = txn.attrib.get("protocol", "http")
    host = txn.attrib.get("host", "")
    path = txn.attrib.get("path", "")
    query = txn.attrib.get("query") or None
    protocol_version = txn.attrib.get("protocolVersion") or None
    port = _parse_int(txn.attrib.get("port"))
    actual_port = _parse_int(txn.attrib.get("actualPort"))
    start_ms = _parse_int(txn.attrib.get("startTimeMillis"))
    response_ms = _parse_int(txn.attrib.get("responseTimeMillis"))
    end_ms = _parse_int(txn.attrib.get("endTimeMillis"))
    timing_summary = {
        "start_time": txn.attrib.get("startTime"),
        "start_time_ms": start_ms,
        "response_time": txn.attrib.get("responseTime"),
        "response_time_ms": response_ms,
        "end_time": txn.attrib.get("endTime"),
        "end_time_ms": end_ms,
    }
    if start_ms is not None and end_ms is not None:
        timing_summary["total_ms"] = max(end_ms - start_ms, 0)

    request_el = txn.find("request")
    response_el = txn.find("response")
    if request_el is None or response_el is None:
        raise ValueError("Each transaction must contain request and response nodes")

    request_headers, request_first_line = _parse_headers(request_el.find("headers"))
    response_headers, response_first_line = _parse_headers(response_el.find("headers"))

    request_body = _parse_body_blob(
        request_el.find("body"),
        body_blob_id=build_body_blob_id(capture_id, sequence_no, "request"),
        charset=request_el.attrib.get("charset"),
    )
    response_body = _parse_body_blob(
        response_el.find("body"),
        body_blob_id=build_body_blob_id(capture_id, sequence_no, "response"),
        charset=response_el.attrib.get("charset"),
    )

    size_summary = {
        "request_body_bytes": request_body.byte_length,
        "response_body_bytes": response_body.byte_length,
    }

    response_status = _parse_int(response_el.attrib.get("status"))
    entry_id = _build_entry_id(
        capture_id=capture_id,
        sequence_no=sequence_no,
        method=method,
        protocol=protocol,
        host=host,
        path=path,
        query=query or "",
        start_ms=start_ms,
    )

    entry = Entry(
        entry_id=entry_id,
        capture_id=capture_id,
        sequence_no=sequence_no,
        method=method,
        scheme=protocol,
        host=host,
        path=path,
        query=query,
        status_code=response_status,
        timing_summary=timing_summary,
        size_summary=size_summary,
        metadata={
            "protocol_version": protocol_version,
            "port": port,
            "actual_port": actual_port,
            "remote_address": txn.attrib.get("remoteAddress"),
            "client_address": txn.attrib.get("clientAddress"),
        },
    )
    request = Request(
        request_id=f"{entry_id}:request",
        entry_id=entry_id,
        first_line=request_first_line,
        http_version=protocol_version,
        headers=request_headers,
        cookies=parse_cookie_header(request_headers.get("cookie")),
        content_type=header_value(request_headers, "content-type"),
        content_encoding=header_value(request_headers, "content-encoding"),
        body_blob_id=request_body.body_blob_id if request_body.byte_length or request_body.raw_text else None,
        raw_header_hash=hash_headers(request_headers),
        metadata={
            "xml_headers_present": request_el.attrib.get("headers"),
            "xml_body_present": request_el.attrib.get("body"),
        },
    )
    response = Response(
        response_id=f"{entry_id}:response",
        entry_id=entry_id,
        status_code=response_status,
        reason_phrase=reason_phrase(response_first_line),
        headers=response_headers,
        set_cookies=parse_set_cookie_headers(response_headers.get("set-cookie")),
        content_type=response_el.attrib.get("mime-type") or header_value(response_headers, "content-type"),
        content_encoding=header_value(response_headers, "content-encoding"),
        body_blob_id=response_body.body_blob_id if response_body.byte_length or response_body.raw_text else None,
        redirect_location=header_value(response_headers, "location"),
        raw_header_hash=hash_headers(response_headers),
        metadata={
            "xml_headers_present": response_el.attrib.get("headers"),
            "xml_body_present": response_el.attrib.get("body"),
        },
    )

    body_blobs = []
    if request.body_blob_id:
        body_blobs.append(request_body)
    if response.body_blob_id:
        body_blobs.append(response_body)
    return ImportedEntryGraph(entry=entry, request=request, response=response, body_blobs=body_blobs)


def _parse_headers(headers_el: ET.Element | None) -> tuple[dict[str, list[str]], str | None]:
    if headers_el is None:
        return {}, None

    headers: dict[str, list[str]] = {}
    first_line = headers_el.findtext("first-line")
    for header_el in headers_el.findall("header"):
        name = (header_el.findtext("name") or "").strip()
        value = header_el.findtext("value") or ""
        if not name:
            continue
        headers.setdefault(name.lower(), []).append(value)
    return headers, first_line


def _parse_body_blob(body_el: ET.Element | None, *, body_blob_id: str, charset: str | None) -> BodyBlob:
    if body_el is None:
        return BodyBlob(
            body_blob_id=body_blob_id,
            storage_kind=BodyStorageKind.INLINE,
            preservation_level=BodyPreservationLevel.MISSING,
            charset=charset,
            metadata={"encoding": None},
        )

    encoding = (body_el.attrib.get("encoding") or "").lower()
    text = body_el.text or ""
    metadata = {"encoding": encoding}
    if not text:
        return BodyBlob(
            body_blob_id=body_blob_id,
            storage_kind=BodyStorageKind.INLINE,
            preservation_level=BodyPreservationLevel.MISSING,
            charset=charset,
            metadata=metadata,
        )

    if encoding == "base64":
        raw_bytes = base64.b64decode(text, validate=False)
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        return BodyBlob(
            body_blob_id=body_blob_id,
            storage_kind=BodyStorageKind.INLINE,
            byte_length=len(raw_bytes),
            text_length=None,
            sha256=sha256,
            is_binary=True,
            charset=charset,
            raw_bytes=raw_bytes,
            preservation_level=BodyPreservationLevel.RAW,
            metadata=metadata,
        )

    raw_bytes = text.encode(charset or "utf-8", errors="replace")
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return BodyBlob(
        body_blob_id=body_blob_id,
        storage_kind=BodyStorageKind.INLINE,
        byte_length=len(raw_bytes),
        text_length=len(text),
        sha256=sha256,
        is_binary=False,
        charset=charset,
        raw_bytes=raw_bytes,
        raw_text=text,
        preservation_level=BodyPreservationLevel.RAW,
        metadata=metadata,
    )


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None

def _build_entry_id(
    *,
    capture_id: str,
    sequence_no: int,
    method: str,
    protocol: str,
    host: str,
    path: str,
    query: str,
    start_ms: int | None,
) -> str:
    payload = "|".join(
        [
            capture_id,
            str(sequence_no),
            method,
            protocol,
            host,
            path,
            query,
            str(start_ms or ""),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

