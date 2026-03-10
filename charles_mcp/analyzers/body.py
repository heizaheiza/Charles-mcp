"""Body parsing and preview helpers."""

from __future__ import annotations

import base64
import gzip
import json
import re
from typing import Any
from urllib.parse import parse_qs

from charles_mcp.schemas.traffic import BodyContent

_TEXTUAL_MIME_HINTS = (
    "json",
    "xml",
    "javascript",
    "text/",
    "application/graphql",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
)


def normalize_body(
    message: dict | None,
    header_map: dict[str, list[str]],
    *,
    include_full_body: bool = False,
    max_preview_chars: int = 256,
    max_full_body_chars: int = 4096,
    prefix: str = "body",
) -> BodyContent:
    """Normalize a Charles body into a structured content model."""
    message = message or {}
    body = message.get("body") or {}
    raw_text = body.get("text")
    encoded = bool(body.get("encoded"))
    header_content_type = _header_value(header_map, "content-type")
    mime_type = _first_non_empty(
        message.get("mimeType"),
        header_content_type,
    )
    if (
        mime_type
        and mime_type.lower().startswith("multipart/form-data")
        and "boundary=" not in mime_type.lower()
        and header_content_type
        and "boundary=" in header_content_type.lower()
    ):
        mime_type = header_content_type
    charset = message.get("charset")
    content_encoding = _first_non_empty(
        message.get("contentEncoding"),
        _header_value(header_map, "content-encoding"),
    )
    size_bytes = _read_size(message)

    result = BodyContent(
        kind="none",
        mime_type=mime_type,
        charset=charset,
        content_encoding=content_encoding,
        size_bytes=size_bytes,
    )

    if raw_text in (None, ""):
        if encoded:
            result.kind = "base64"
        return result

    text = str(raw_text)
    warnings: list[str] = []

    if encoded:
        decoded_text, decoded_warnings = _decode_encoded_body(
            text,
            mime_type=mime_type,
            charset=charset,
            content_encoding=content_encoding,
        )
        warnings.extend(decoded_warnings)
        if decoded_text is not None:
            text = decoded_text
            result.kind = "base64"

    if content_encoding and content_encoding.lower() == "gzip":
        decompressed, gzip_warnings = _decode_gzip_text(text, charset=charset)
        warnings.extend(gzip_warnings)
        if decompressed is not None:
            text = decompressed

    result.decode_warnings.extend(warnings)
    lower_mime = (mime_type or "").lower()

    if "application/json" in lower_mime or _looks_like_json(text):
        result.kind = "json"
        try:
            parsed = json.loads(text)
            result.parsed_json = parsed
            rendered = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
            result.preview_text, result.preview_truncated = _clip_text(
                rendered,
                max_chars=max_preview_chars,
            )
            if include_full_body:
                result.full_text, result.full_text_truncated = _clip_text(
                    rendered,
                    max_chars=max_full_body_chars,
                )
            return result
        except Exception:
            result.decode_warnings.append("json_parse_failed")

    if "application/x-www-form-urlencoded" in lower_mime:
        result.kind = "form"
        parsed_form = parse_qs(text, keep_blank_values=True)
        result.parsed_form = parsed_form
        rendered = "&".join(
            f"{key}={','.join(values)}" for key, values in sorted(parsed_form.items())
        )
        result.preview_text, result.preview_truncated = _clip_text(
            rendered,
            max_chars=max_preview_chars,
        )
        if include_full_body:
            result.full_text, result.full_text_truncated = _clip_text(
                rendered,
                max_chars=max_full_body_chars,
            )
        return result

    if "multipart/form-data" in lower_mime:
        result.kind = "multipart"
        summary, multipart_warnings = _summarize_multipart(
            text,
            mime_type=mime_type,
        )
        result.multipart_summary = summary
        result.decode_warnings.extend(multipart_warnings)
        result.preview_text = f"[multipart/form-data with {len(summary)} part(s)]"
        if include_full_body:
            result.full_text, result.full_text_truncated = _clip_text(
                text,
                max_chars=max_full_body_chars,
            )
        return result

    if _is_textual(mime_type) or _looks_like_text(text):
        result.kind = "text"
        result.preview_text, result.preview_truncated = _clip_text(
            text,
            max_chars=max_preview_chars,
        )
        if include_full_body:
            result.full_text, result.full_text_truncated = _clip_text(
                text,
                max_chars=max_full_body_chars,
            )
        return result

    result.kind = "binary"
    result.preview_text = "[binary body omitted]"
    return result


def _decode_encoded_body(
    text: str,
    *,
    mime_type: str | None,
    charset: str | None,
    content_encoding: str | None,
) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    try:
        payload = base64.b64decode(text, validate=False)
    except Exception:
        return None, ["base64_decode_failed"]

    if content_encoding and content_encoding.lower() == "gzip":
        try:
            payload = gzip.decompress(payload)
        except Exception:
            warnings.append("gzip_decompress_failed")

    if not _is_textual(mime_type):
        return None, warnings

    encoding = charset or "utf-8"
    try:
        return payload.decode(encoding, errors="replace"), warnings
    except Exception:
        return payload.decode("utf-8", errors="replace"), warnings + ["body_decode_fallback_utf8"]


def _decode_gzip_text(text: str, *, charset: str | None) -> tuple[str | None, list[str]]:
    try:
        payload = gzip.decompress(text.encode("latin1"))
    except Exception:
        return None, ["gzip_text_decode_failed"]

    try:
        return payload.decode(charset or "utf-8", errors="replace"), []
    except Exception:
        return payload.decode("utf-8", errors="replace"), ["body_decode_fallback_utf8"]


def _read_size(message: dict[str, Any]) -> int | None:
    sizes = message.get("sizes")
    if isinstance(sizes, dict):
        body_size = sizes.get("body")
        if isinstance(body_size, int):
            return body_size
    return None


def _header_value(header_map: dict[str, list[str]], name: str) -> str | None:
    values = header_map.get(name.lower())
    if not values:
        return None
    return values[0] or None


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _is_textual(mime_type: str | None) -> bool:
    lower_mime = (mime_type or "").lower()
    return any(hint in lower_mime for hint in _TEXTUAL_MIME_HINTS)


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("{") or stripped.startswith("[")


def _looks_like_text(text: str) -> bool:
    if not text:
        return False
    sample = text[:128]
    non_printable = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\r\n\t")
    return non_printable < max(len(sample) // 10, 1)


def _clip_text(text: str, *, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _summarize_multipart(text: str, *, mime_type: str | None) -> tuple[list[dict[str, Any]], list[str]]:
    boundary = _extract_boundary(mime_type)
    if not boundary:
        return [], ["multipart_boundary_missing"]

    summary: list[dict[str, Any]] = []
    warnings: list[str] = []
    delimiter = f"--{boundary}"
    parts = text.split(delimiter)

    for part in parts:
        candidate = part.strip("\r\n")
        if not candidate or candidate == "--":
            continue
        if candidate.endswith("--"):
            candidate = candidate[:-2].rstrip("\r\n")
        header_blob, separator, body_blob = candidate.partition("\r\n\r\n")
        if not separator:
            header_blob, separator, body_blob = candidate.partition("\n\n")
        if not separator:
            warnings.append("multipart_part_separator_missing")
            continue

        headers = _parse_part_headers(header_blob)
        disposition = headers.get("content-disposition", "")
        name = _extract_disposition_value(disposition, "name")
        filename = _extract_disposition_value(disposition, "filename")
        content_type = headers.get("content-type")
        body_text = body_blob.rstrip("\r\n")
        preview, truncated = _clip_text(body_text, max_chars=80)
        summary.append(
            {
                "name": name,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(body_text.encode("utf-8", errors="ignore")),
                "preview_text": preview if preview else None,
                "preview_truncated": truncated,
            }
        )

    if not summary:
        warnings.append("multipart_body_not_parsed")
    return summary, warnings


def _extract_boundary(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    match = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', mime_type, re.IGNORECASE)
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip()


def _parse_part_headers(header_blob: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in header_blob.splitlines():
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return headers


def _extract_disposition_value(disposition: str, key: str) -> str | None:
    match = re.search(rf'{re.escape(key)}="([^"]+)"', disposition, re.IGNORECASE)
    if not match:
        return None
    return match.group(1)
