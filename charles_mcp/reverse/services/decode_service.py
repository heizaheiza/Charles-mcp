"""Decode request/response bodies from canonical entries."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs

import brotli
import zstandard
from google.protobuf import descriptor_pb2, descriptor_pool, json_format, message_factory

from charles_mcp.reverse.models import ArtifactType, DecodedArtifact
from charles_mcp.reverse.services.common import new_identifier
from charles_mcp.reverse.storage import SQLiteStore


class DecodeService:
    """Decode stored body blobs into structured artifacts."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def decode_entry_body(
        self,
        *,
        entry_id: str,
        side: str,
        descriptor_path: str | None = None,
        message_type: str | None = None,
    ) -> dict:
        snapshot = self.store.get_entry_snapshot(entry_id)
        if snapshot is None:
            raise ValueError(f"entry `{entry_id}` was not found")

        side_key = side.lower()
        if side_key not in {"request", "response"}:
            raise ValueError("side must be `request` or `response`")

        message = snapshot[side_key]
        if message is None:
            raise ValueError(f"entry `{entry_id}` does not have a {side_key}")
        body_blob = snapshot[f"{side_key}_body_blob"]
        if body_blob is None:
            raise ValueError(f"entry `{entry_id}` {side_key} body is empty")

        raw_bytes = body_blob.raw_bytes or (body_blob.raw_text or "").encode(
            body_blob.charset or "utf-8",
            errors="replace",
        )
        content_encoding = (message.content_encoding or "").lower()
        content_type = (message.content_type or "").lower()
        warnings: list[str] = []

        payload = raw_bytes
        if content_encoding == "gzip":
            payload, warning = _try_decompress_gzip(payload)
            if warning:
                warnings.append(warning)
        elif content_encoding == "br":
            payload, warning = _try_decompress_brotli(payload)
            if warning:
                warnings.append(warning)
        elif content_encoding == "zstd":
            payload, warning = _try_decompress_zstd(payload)
            if warning:
                warnings.append(warning)
        elif content_encoding not in {"", "identity"}:
            warnings.append(f"unhandled_content_encoding:{content_encoding}")

        artifact_type = ArtifactType.OPAQUE_BINARY
        structured_json: dict[str, Any] | list[Any] | None = None
        preview_text: str | None = None

        if "application/json" in content_type or _looks_like_json_bytes(payload):
            decoded_text = payload.decode(body_blob.charset or "utf-8", errors="replace")
            try:
                artifact_type = ArtifactType.JSON
                structured_json = json.loads(decoded_text)
                preview_text = json.dumps(structured_json, ensure_ascii=False, separators=(",", ":"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                warnings.append("json_decode_failed")
                structured_json = None
                text = _try_decode_text(payload, body_blob.charset)
                if text is not None:
                    artifact_type = ArtifactType.PLAIN_TEXT
                    preview_text = text
                else:
                    artifact_type = ArtifactType.OPAQUE_BINARY
                    preview_text = payload[:128].hex()
        elif "application/x-www-form-urlencoded" in content_type:
            artifact_type = ArtifactType.FORM
            structured_json = parse_qs(payload.decode(body_blob.charset or "utf-8", errors="replace"), keep_blank_values=True)
            preview_text = "&".join(
                f"{key}={','.join(values)}" for key, values in sorted(structured_json.items())
            )
        elif "multipart/form-data" in content_type:
            artifact_type = ArtifactType.MULTIPART
            preview_text = payload.decode(body_blob.charset or "utf-8", errors="replace")[:512]
            warnings.append("multipart_preview_only")
        elif "protobuf" in content_type or "x-protobuf" in content_type:
            artifact_type = ArtifactType.PROTOBUF
            if not descriptor_path or not message_type:
                warnings.append("protobuf_descriptor_required")
                preview_text = payload[:128].hex()
            else:
                structured_json = _decode_protobuf_payload(
                    payload=payload,
                    descriptor_path=descriptor_path,
                    message_type=message_type,
                )
                preview_text = json.dumps(structured_json, ensure_ascii=False, separators=(",", ":"))
        else:
            text = _try_decode_text(payload, body_blob.charset)
            if text is not None:
                artifact_type = ArtifactType.PLAIN_TEXT
                preview_text = text
            else:
                artifact_type = ArtifactType.OPAQUE_BINARY
                preview_text = payload[:128].hex()

        artifact = DecodedArtifact(
            artifact_id=new_identifier("artifact"),
            body_blob_id=body_blob.body_blob_id,
            artifact_type=artifact_type,
            decoder_name="vnext.decode",
            decoder_version="0.1",
            descriptor_ref=descriptor_path,
            preview_text=_clip(preview_text, 2048) if preview_text else None,
            structured_json=structured_json,
            warnings=warnings,
            confidence=1.0 if not warnings else 0.7,
            metadata={
                "entry_id": entry_id,
                "side": side_key,
                "content_type": content_type,
                "content_encoding": content_encoding,
            },
        )
        self.store.upsert_decoded_artifact(artifact)
        return artifact.model_dump(mode="json", exclude_none=True)


def _looks_like_json_bytes(payload: bytes) -> bool:
    stripped = payload.lstrip()
    return stripped.startswith(b"{") or stripped.startswith(b"[")


def _try_decode_text(payload: bytes, charset: str | None) -> str | None:
    try:
        text = payload.decode(charset or "utf-8", errors="replace")
    except Exception:
        return None
    sample = text[:128]
    non_printable = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\r\n\t")
    if non_printable > max(len(sample) // 10, 1):
        return None
    return text


def _decode_protobuf_payload(
    *,
    payload: bytes,
    descriptor_path: str,
    message_type: str,
) -> dict[str, Any]:
    descriptor_data = Path(descriptor_path).read_bytes()
    file_set = descriptor_pb2.FileDescriptorSet()
    file_set.ParseFromString(descriptor_data)

    pool = descriptor_pool.DescriptorPool()
    for file_proto in file_set.file:
        pool.Add(file_proto)

    descriptor = pool.FindMessageTypeByName(message_type)
    message_cls = message_factory.GetMessageClass(descriptor)
    message = message_cls()
    message.ParseFromString(payload)
    return cast(
        dict[str, Any],
        json_format.MessageToDict(message, preserving_proto_field_name=True),
    )


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit]


def _try_decompress_gzip(payload: bytes) -> tuple[bytes, str | None]:
    try:
        return gzip.decompress(payload), None
    except Exception:
        return payload, "gzip_header_present_but_payload_not_compressed"


def _try_decompress_brotli(payload: bytes) -> tuple[bytes, str | None]:
    try:
        return brotli.decompress(payload), None
    except Exception:
        return payload, "brotli_header_present_but_payload_not_compressed"


def _try_decompress_zstd(payload: bytes) -> tuple[bytes, str | None]:
    try:
        return zstandard.ZstdDecompressor().decompress(payload), None
    except Exception:
        return payload, "zstd_header_present_but_payload_not_compressed"

