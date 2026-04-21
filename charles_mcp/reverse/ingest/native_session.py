"""Direct ingestion for native Charles session archives."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
class NativeImportedEntryGraph:
    entry: Entry
    request: Request
    response: Response
    body_blobs: list[BodyBlob]


@dataclass
class NativeImportedCaptureGraph:
    capture: Capture
    entries: list[NativeImportedEntryGraph]
    warnings: list[str]


def parse_charles_native_session(
    path: str | Path,
    *,
    capture_id: str,
    source_kind: CaptureSourceKind,
) -> NativeImportedCaptureGraph:
    """Parse a downloaded Charles native session archive into canonical entities."""
    archive_path = Path(path)
    entries: list[NativeImportedEntryGraph] = []
    warnings: list[str] = []

    with zipfile.ZipFile(archive_path) as zf:
        meta_names = sorted(
            [name for name in zf.namelist() if name.endswith("-meta.json")],
            key=_archive_sequence,
        )
        for sequence_no, meta_name in enumerate(meta_names, start=1):
            meta = json.loads(zf.read(meta_name).decode("utf-8"))
            prefix = meta_name[: -len("-meta.json")]
            entries.append(
                _parse_archive_entry(
                    zf,
                    meta=meta,
                    prefix=prefix,
                    capture_id=capture_id,
                    sequence_no=sequence_no,
                )
            )

    capture = Capture(
        capture_id=capture_id,
        source_kind=source_kind,
        source_format=CaptureSourceFormat.NATIVE,
        ingest_status="ready",
        entry_count=len(entries),
        metadata={"source_path": str(archive_path)},
    )
    return NativeImportedCaptureGraph(capture=capture, entries=entries, warnings=warnings)


def _parse_archive_entry(
    zf: zipfile.ZipFile,
    *,
    meta: dict,
    prefix: str,
    capture_id: str,
    sequence_no: int,
) -> NativeImportedEntryGraph:
    method = meta.get("method", "GET")
    scheme = meta.get("scheme") or "http"
    host = meta.get("host", "")
    path = meta.get("path") or ""
    query = meta.get("query")
    start_ms = _nested_int(meta, "times", "startMillis")
    if start_ms is None:
        start_ms = _timestamp_to_int(meta.get("times", {}).get("start"))
    end_ms = _nested_int(meta, "times", "endMillis")
    if end_ms is None:
        end_ms = _timestamp_to_int(meta.get("times", {}).get("end"))

    entry_id = _build_entry_id(
        capture_id=capture_id,
        sequence_no=sequence_no,
        method=method,
        scheme=scheme,
        host=host,
        path=path,
        query=query or "",
        start_marker=start_ms if start_ms is not None else meta.get("times", {}).get("start"),
    )

    request_meta = meta.get("request") or {}
    response_meta = meta.get("response") or {}
    request_headers = _header_map(request_meta.get("header", {}).get("headers"))
    response_headers = _header_map(response_meta.get("header", {}).get("headers"))

    request_body = _read_body_blob(
        zf,
        prefix=prefix,
        side="req",
        body_blob_id=build_body_blob_id(capture_id, sequence_no, "request"),
        charset=request_meta.get("charset"),
        body_size=_nested_int(request_meta, "sizes", "body"),
    )
    response_body = _read_body_blob(
        zf,
        prefix=prefix,
        side="res",
        body_blob_id=build_body_blob_id(capture_id, sequence_no, "response"),
        charset=response_meta.get("charset"),
        body_size=_nested_int(response_meta, "sizes", "body"),
    )

    entry = Entry(
        entry_id=entry_id,
        capture_id=capture_id,
        sequence_no=sequence_no,
        method=method,
        scheme=scheme,
        host=host,
        path=path,
        query=query,
        status_code=response_meta.get("status"),
        timing_summary={
            "start_time": meta.get("times", {}).get("start"),
            "start_time_ms": start_ms,
            "request_begin_time": meta.get("times", {}).get("requestBegin"),
            "request_complete_time": meta.get("times", {}).get("requestComplete"),
            "response_begin_time": meta.get("times", {}).get("responseBegin"),
            "end_time": meta.get("times", {}).get("end"),
            "end_time_ms": end_ms,
            "total_ms": _nested_int(meta, "durations", "total"),
        },
        size_summary={
            "request_body_bytes": _nested_int(request_meta, "sizes", "body"),
            "response_body_bytes": _nested_int(response_meta, "sizes", "body"),
            "total_size": meta.get("totalSize"),
        },
        metadata={
            "protocol_version": meta.get("protocolVersion"),
            "port": meta.get("port"),
            "actual_port": meta.get("actualPort"),
            "remote_address": meta.get("remoteAddress"),
            "client_address": meta.get("clientAddress"),
            "client_port": meta.get("clientPort"),
            "status": meta.get("status"),
        },
    )
    request = Request(
        request_id=f"{entry_id}:request",
        entry_id=entry_id,
        first_line=request_meta.get("header", {}).get("firstLine"),
        http_version=meta.get("protocolVersion"),
        headers=request_headers,
        cookies=parse_cookie_header(request_headers.get("cookie")),
        content_type=request_meta.get("mimeType") or header_value(request_headers, "content-type"),
        content_encoding=request_meta.get("contentEncoding") or header_value(request_headers, "content-encoding"),
        body_blob_id=request_body.body_blob_id if request_body else None,
        raw_header_hash=hash_headers(request_headers),
        metadata={"archive_prefix": prefix},
    )
    response = Response(
        response_id=f"{entry_id}:response",
        entry_id=entry_id,
        status_code=response_meta.get("status"),
        reason_phrase=reason_phrase(response_meta.get("header", {}).get("firstLine")),
        headers=response_headers,
        set_cookies=parse_set_cookie_headers(response_headers.get("set-cookie")),
        content_type=response_meta.get("mimeType") or header_value(response_headers, "content-type"),
        content_encoding=response_meta.get("contentEncoding") or header_value(response_headers, "content-encoding"),
        body_blob_id=response_body.body_blob_id if response_body else None,
        redirect_location=header_value(response_headers, "location"),
        raw_header_hash=hash_headers(response_headers),
        metadata={"archive_prefix": prefix},
    )
    body_blobs = [blob for blob in (request_body, response_body) if blob is not None]
    return NativeImportedEntryGraph(
        entry=entry,
        request=request,
        response=response,
        body_blobs=body_blobs,
    )


def _archive_sequence(name: str) -> int:
    return int(name.split("-", 1)[0])


def _read_body_blob(
    zf: zipfile.ZipFile,
    *,
    prefix: str,
    side: str,
    body_blob_id: str,
    charset: str | None,
    body_size: int | None,
) -> BodyBlob | None:
    sidecar = _find_sidecar_name(zf, prefix, side)
    if sidecar is None and not body_size:
        return None

    raw_bytes = zf.read(sidecar) if sidecar else b""
    extension = Path(sidecar).suffix.lower() if sidecar else ""
    is_textual = extension in {".json", ".txt", ".html", ".xml", ".csv"}
    raw_text = raw_bytes.decode(charset or "utf-8", errors="replace") if raw_bytes and is_textual else None
    return BodyBlob(
        body_blob_id=body_blob_id,
        storage_kind=BodyStorageKind.INLINE,
        byte_length=len(raw_bytes) if raw_bytes else body_size,
        text_length=len(raw_text) if raw_text is not None else None,
        sha256=hashlib.sha256(raw_bytes).hexdigest() if raw_bytes else None,
        is_binary=not is_textual,
        charset=charset,
        raw_bytes=raw_bytes or None,
        raw_text=raw_text,
        preservation_level=BodyPreservationLevel.RAW if raw_bytes or raw_text else BodyPreservationLevel.MISSING,
        metadata={"sidecar": sidecar, "extension": extension},
    )


def _find_sidecar_name(zf: zipfile.ZipFile, prefix: str, side: str) -> str | None:
    for extension in (".json", ".txt", ".html", ".dat", ".xml", ".csv"):
        name = f"{prefix}-{side}{extension}"
        if name in zf.namelist():
            return name
    return None


def _header_map(headers: list[dict] | None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for header in headers or []:
        name = str(header.get("name") or "").strip()
        value = str(header.get("value") or "")
        if not name:
            continue
        result.setdefault(name.lower(), []).append(value)
    return result


def _nested_int(payload: dict, *path: str) -> int | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, int) else None


def _timestamp_to_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        # Python 3.10's fromisoformat() does not accept the trailing "Z" UTC designator.
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)

def _build_entry_id(
    *,
    capture_id: str,
    sequence_no: int,
    method: str,
    scheme: str,
    host: str,
    path: str,
    query: str,
    start_marker: str | int | None,
) -> str:
    payload = "|".join(
        [
            capture_id,
            str(sequence_no),
            str(method or ""),
            str(scheme or ""),
            str(host or ""),
            str(path or ""),
            str(query or ""),
            str(start_marker or ""),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

