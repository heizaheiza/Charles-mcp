"""Traffic query and summary logic."""

from __future__ import annotations

from functools import lru_cache

import jmespath

from charles_mcp.analyzers.headers import build_header_highlights
from charles_mcp.schemas.analysis import CaptureAnalysisStatsResult
from charles_mcp.schemas.traffic import (
    CaptureSource,
    HttpMessage,
    ResourceClass,
    TrafficDetail,
    TrafficEntry,
    TrafficMatch,
    TrafficSummary,
)
from charles_mcp.schemas.traffic_query import TrafficQuery


class TrafficAnalysisService:
    """Apply structured filters and build summary/detail views."""

    def match_entry(self, entry: TrafficEntry, query: TrafficQuery) -> TrafficMatch:
        matched_fields: list[str] = []
        match_reasons: list[str] = []

        if query.host_contains and query.host_contains.lower() not in (entry.host or "").lower():
            return TrafficMatch(matched=False)
        if query.host_contains:
            matched_fields.append("host")
            match_reasons.append(f"host contains `{query.host_contains}`")

        if query.path_contains and query.path_contains.lower() not in (entry.path or "").lower():
            return TrafficMatch(matched=False)
        if query.path_contains:
            matched_fields.append("path")
            match_reasons.append(f"path contains `{query.path_contains}`")

        if query.method_in:
            methods = {item.upper() for item in query.method_in}
            if (entry.method or "").upper() not in methods:
                return TrafficMatch(matched=False)
            matched_fields.append("method")
            match_reasons.append("method matches selection")

        if query.status_in:
            if entry.response_status not in set(query.status_in):
                return TrafficMatch(matched=False)
            matched_fields.append("response_status")
            match_reasons.append("response status matches selection")

        has_error = bool(entry.error_message) or (entry.response_status or 0) >= 400
        if query.has_error is not None and has_error != query.has_error:
            return TrafficMatch(matched=False)
        if query.has_error:
            matched_fields.append("error")
            match_reasons.append("entry has error signal")

        if query.resource_class_in and entry.resource_class not in set(query.resource_class_in):
            return TrafficMatch(matched=False)
        if query.resource_class_in:
            matched_fields.append("resource_class")
            match_reasons.append("resource class matches selection")

        if query.min_priority_score is not None and entry.priority_score < query.min_priority_score:
            return TrafficMatch(matched=False)
        if query.min_priority_score is not None:
            matched_fields.append("priority_score")
            match_reasons.append(f"priority score >= {query.min_priority_score}")

        if query.request_header_name or query.request_header_value_contains:
            if not self._match_header(
                entry.request.header_map,
                query.request_header_name,
                query.request_header_value_contains,
            ):
                return TrafficMatch(matched=False)
            matched_fields.append("request.headers")
            match_reasons.append("request header filter matched")

        if query.response_header_name or query.response_header_value_contains:
            if not self._match_header(
                entry.response.header_map,
                query.response_header_name,
                query.response_header_value_contains,
            ):
                return TrafficMatch(matched=False)
            matched_fields.append("response.headers")
            match_reasons.append("response header filter matched")

        if query.request_content_type and query.request_content_type.lower() not in (
            entry.request.mime_type or ""
        ).lower():
            return TrafficMatch(matched=False)
        if query.request_content_type:
            matched_fields.append("request.content_type")
            match_reasons.append("request content-type matched")

        if query.response_content_type and query.response_content_type.lower() not in (
            entry.response.mime_type or ""
        ).lower():
            return TrafficMatch(matched=False)
        if query.response_content_type:
            matched_fields.append("response.content_type")
            match_reasons.append("response content-type matched")

        if query.request_body_contains and not self._contains_text(
            self._body_text(entry.request),
            query.request_body_contains,
        ):
            return TrafficMatch(matched=False)
        if query.request_body_contains:
            matched_fields.append("request.body")
            match_reasons.append("request body matched")

        if query.response_body_contains and not self._contains_text(
            self._body_text(entry.response),
            query.response_body_contains,
        ):
            return TrafficMatch(matched=False)
        if query.response_body_contains:
            matched_fields.append("response.body")
            match_reasons.append("response body matched")

        if query.request_json_query and not self._match_json_query(
            entry.request.body.parsed_json,
            query.request_json_query,
        ):
            return TrafficMatch(matched=False)
        if query.request_json_query:
            matched_fields.append("request.body.json")
            match_reasons.append("request JSON query matched")

        if query.response_json_query and not self._match_json_query(
            entry.response.body.parsed_json,
            query.response_json_query,
        ):
            return TrafficMatch(matched=False)
        if query.response_json_query:
            matched_fields.append("response.body.json")
            match_reasons.append("response JSON query matched")

        if query.min_total_size is not None and (entry.total_size or 0) < query.min_total_size:
            return TrafficMatch(matched=False)
        if query.min_total_size is not None:
            matched_fields.append("total_size")
            match_reasons.append(f"total size >= {query.min_total_size}")

        if query.max_total_size is not None and (entry.total_size or 0) > query.max_total_size:
            return TrafficMatch(matched=False)
        if query.max_total_size is not None:
            matched_fields.append("total_size")
            match_reasons.append(f"total size <= {query.max_total_size}")

        if not matched_fields:
            match_reasons.append(f"matched preset `{query.preset}`")

        return TrafficMatch(
            matched=True,
            matched_fields=matched_fields,
            match_reasons=match_reasons,
        )

    def summarize_entry(
        self,
        entry: TrafficEntry,
        match: TrafficMatch,
        *,
        max_headers_per_side: int = 8,
        include_body_preview: bool = True,
    ) -> TrafficSummary:
        return TrafficSummary(
            entry_id=entry.entry_id,
            capture_source=entry.capture_source,
            capture_id=entry.capture_id,
            recording_path=entry.recording_path,
            resource_class=entry.resource_class,
            priority_score=entry.priority_score,
            method=entry.method,
            host=entry.host,
            path=entry.path,
            response_status=entry.response_status,
            request_content_type=entry.request.mime_type,
            response_content_type=entry.response.mime_type,
            total_size=entry.total_size,
            has_error=bool(entry.error_message) or (entry.response_status or 0) >= 400,
            error_message=entry.error_message,
            request_header_highlights=build_header_highlights(
                entry.request.header_map,
                max_items=max_headers_per_side,
            ),
            response_header_highlights=build_header_highlights(
                entry.response.header_map,
                max_items=max_headers_per_side,
            ),
            request_body_preview=entry.request.body.preview_text if include_body_preview else None,
            response_body_preview=entry.response.body.preview_text if include_body_preview else None,
            preview_truncated=entry.request.body.preview_truncated
            or entry.response.body.preview_truncated,
            matched_fields=match.matched_fields,
            match_reasons=match.match_reasons,
            detail_available=True,
        )

    def build_detail(self, entry: TrafficEntry) -> TrafficDetail:
        entry = self._compact_entry_for_detail(entry)
        return TrafficDetail(
            entry=entry,
            raw_body_included=bool(
                entry.request.body.full_text is not None or entry.response.body.full_text is not None
            ),
            body_truncated=entry.request.body.full_text_truncated
            or entry.response.body.full_text_truncated
            or entry.request.body.preview_truncated
            or entry.response.body.preview_truncated,
        )

    @staticmethod
    def _compact_entry_for_detail(entry: TrafficEntry) -> TrafficEntry:
        """Strip redundant preview fields when full_text is present."""
        updates: dict = {}
        for side in ("request", "response"):
            msg: HttpMessage = getattr(entry, side)
            body = msg.body
            if body.full_text is not None and body.preview_text is not None:
                compact_body = body.model_copy(
                    update={"preview_text": None, "preview_truncated": False},
                )
                updates[side] = msg.model_copy(update={"body": compact_body})
        if updates:
            return entry.model_copy(update=updates)
        return entry

    def build_stats(
        self,
        *,
        source: CaptureSource,
        preset: str,
        total_items: int,
        scanned_count: int,
        classified_counts: dict[ResourceClass, int],
        warnings: list[str] | None = None,
    ) -> CaptureAnalysisStatsResult:
        return CaptureAnalysisStatsResult(
            source=source,
            preset=preset,
            total_items=total_items,
            scanned_count=scanned_count,
            classified_counts=classified_counts,
            warnings=warnings or [],
        )

    @staticmethod
    def _match_header(
        header_map: dict[str, list[str]],
        name: str | None,
        value_contains: str | None,
    ) -> bool:
        if name:
            lower_name = name.lower()
            values = header_map.get(lower_name)
            if not values:
                return False
            if value_contains is None:
                return True
            return any(value_contains.lower() in (value or "").lower() for value in values)

        if value_contains:
            token = value_contains.lower()
            return any(token in (value or "").lower() for values in header_map.values() for value in values)

        return True

    @staticmethod
    def _contains_text(value: str | None, needle: str) -> bool:
        return needle.lower() in (value or "").lower()

    @staticmethod
    def _body_text(message: HttpMessage) -> str | None:
        return message.body.full_text or message.body.preview_text

    @staticmethod
    def _match_json_query(payload: object, expression: str) -> bool:
        if payload is None:
            return False
        result = _compiled_query(expression).search(payload)
        if result is None:
            return False
        if isinstance(result, bool):
            return result
        if isinstance(result, (list, dict, str)):
            return bool(result)
        return True


@lru_cache(maxsize=128)
def _compiled_query(expression: str):
    return jmespath.compile(expression)
