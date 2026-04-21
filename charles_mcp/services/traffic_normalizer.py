"""Normalize raw Charles entries into structured traffic models."""

from __future__ import annotations

from hashlib import sha1
from typing import Any

from charles_mcp.analyzers import classify_entry, normalize_body, normalize_headers
from charles_mcp.config import Config
from charles_mcp.schemas.traffic import CaptureSource, HttpMessage, ResourceClassification, TrafficEntry


class TrafficNormalizer:
    """Convert raw Charles session entries into typed traffic records."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def normalize_entry(
        self,
        raw_entry: dict[str, Any],
        *,
        capture_source: CaptureSource,
        capture_id: str | None = None,
        recording_path: str | None = None,
        include_full_body: bool = False,
        max_preview_chars: int = 256,
        max_headers_per_side: int = 8,
        max_full_body_chars: int = 4096,
        classification: ResourceClassification | None = None,
    ) -> TrafficEntry:
        """Normalize one Charles entry for summary and detail views."""
        classification = classification or classify_entry(raw_entry)
        request = raw_entry.get("request") or {}
        response = raw_entry.get("response") or {}

        request_headers, request_map = normalize_headers(
            (request.get("header") or {}).get("headers"),
        )
        response_headers, response_map = normalize_headers(
            (response.get("header") or {}).get("headers"),
        )

        request_body = normalize_body(
            request,
            request_map,
            include_full_body=include_full_body,
            max_preview_chars=max_preview_chars,
            max_full_body_chars=max_full_body_chars,
            prefix="request.body",
        )
        response_body = normalize_body(
            response,
            response_map,
            include_full_body=include_full_body,
            max_preview_chars=max_preview_chars,
            max_full_body_chars=max_full_body_chars,
            prefix="response.body",
        )

        request_message = HttpMessage(
            first_line=(request.get("header") or {}).get("firstLine"),
            headers=request_headers[:max_headers_per_side],
            header_map=request_map,
            mime_type=request.get("mimeType"),
            charset=request.get("charset"),
            content_encoding=request.get("contentEncoding"),
            body=request_body,
        )
        response_message = HttpMessage(
            first_line=(response.get("header") or {}).get("firstLine"),
            headers=response_headers[:max_headers_per_side],
            header_map=response_map,
            mime_type=response.get("mimeType"),
            charset=response.get("charset"),
            content_encoding=response.get("contentEncoding"),
            body=response_body,
        )

        response_status = response.get("status")
        return TrafficEntry(
            entry_id=self._build_entry_id(
                raw_entry,
                capture_source=capture_source,
                capture_id=capture_id,
                recording_path=recording_path,
            ),
            capture_source=capture_source,
            capture_id=capture_id,
            recording_path=recording_path,
            resource_class=classification.resource_class,
            priority_score=classification.priority_score,
            priority_reasons=classification.priority_reasons,
            method=raw_entry.get("method"),
            scheme=raw_entry.get("scheme"),
            host=raw_entry.get("host"),
            path=raw_entry.get("path"),
            query=raw_entry.get("query"),
            response_status=response_status if isinstance(response_status, int) else None,
            status=raw_entry.get("status"),
            total_size=raw_entry.get("totalSize"),
            error_message=raw_entry.get("errorMessage"),
            notes=raw_entry.get("notes"),
            times=raw_entry.get("times") or {},
            durations=raw_entry.get("durations") or {},
            request=request_message,
            response=response_message,
        )

    def _build_entry_id(
        self,
        raw_entry: dict[str, Any],
        *,
        capture_source: CaptureSource,
        capture_id: str | None,
        recording_path: str | None,
    ) -> str:
        """Build a lightweight fingerprint from key routing fields."""
        times = raw_entry.get("times") or {}
        response = raw_entry.get("response") or {}
        components = [
            capture_source,
            capture_id or "",
            recording_path or "",
            str(raw_entry.get("host") or ""),
            str(raw_entry.get("method") or ""),
            str(raw_entry.get("path") or ""),
            str(raw_entry.get("query") or ""),
            str(raw_entry.get("status") or ""),
            str(response.get("status") or ""),
            str(times.get("start") or ""),
            str(times.get("end") or ""),
            str(raw_entry.get("totalSize") or ""),
        ]
        return sha1("|".join(components).encode("utf-8")).hexdigest()
