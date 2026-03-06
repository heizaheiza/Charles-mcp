"""Shared traffic analysis queries for live and history sources."""

from __future__ import annotations

from collections import Counter

from charles_mcp.analyzers.resource_classifier import classify_entry
from charles_mcp.schemas.analysis import (
    CaptureAnalysisGroupsResult,
    CaptureAnalysisStatsResult,
    TrafficDetailResult,
    TrafficGroupBy,
    TrafficGroupSummary,
    TrafficQueryResult,
)
from charles_mcp.schemas.traffic import TrafficDetail, TrafficEntry
from charles_mcp.schemas.traffic_query import TrafficQuery
from charles_mcp.services.history_capture import RecordingHistoryService
from charles_mcp.services.live_capture import LiveCaptureService
from charles_mcp.services.traffic_analysis import TrafficAnalysisService
from charles_mcp.services.traffic_normalizer import TrafficNormalizer


class TrafficQueryService:
    """Analyze live and recorded traffic through one structured pipeline."""

    def __init__(
        self,
        *,
        live_service: LiveCaptureService,
        history_service: RecordingHistoryService,
        normalizer: TrafficNormalizer,
        analysis_service: TrafficAnalysisService,
    ) -> None:
        self.live_service = live_service
        self.history_service = history_service
        self.normalizer = normalizer
        self.analysis_service = analysis_service
        self._detail_cache: dict[tuple[str, str | None], dict[str, TrafficEntry]] = {}
        self._classified_cache: dict[tuple[str, str | None], dict[str, int]] = {}

    async def analyze_live_capture(
        self,
        *,
        capture_id: str,
        query: TrafficQuery,
        cursor: int | None = None,
    ) -> TrafficQueryResult:
        limit = max(query.max_items * 5, query.max_items, 50)
        live_result = await self.live_service.read(
            capture_id,
            cursor=cursor,
            limit=limit,
            advance=True,
        )
        return self._analyze_entries(
            source="live",
            raw_entries=live_result.items,
            query=query,
            capture_id=capture_id,
            next_cursor=live_result.next_cursor,
            initial_warnings=list(live_result.warnings),
        )

    async def analyze_recorded_traffic(
        self,
        *,
        recording_path: str | None,
        query: TrafficQuery,
    ) -> TrafficQueryResult:
        if recording_path:
            raw_entries = await self.history_service.get_snapshot(recording_path)
            source_path = recording_path
            warnings: list[str] = []
        else:
            try:
                source_path, raw_entries = await self.history_service.load_latest_with_path()
                warnings = []
            except FileNotFoundError:
                return TrafficQueryResult(
                    source="history",
                    items=[],
                    total_items=0,
                    scanned_count=0,
                    matched_count=0,
                    filtered_out_count=0,
                    filtered_out_by_class={},
                    warnings=["no_saved_recordings"],
                )

        result = self._analyze_entries(
            source="history",
            raw_entries=raw_entries,
            query=query,
            recording_path=source_path,
            initial_warnings=warnings,
        )
        return result

    async def get_detail(
        self,
        *,
        source: str,
        entry_id: str,
        capture_id: str | None = None,
        recording_path: str | None = None,
        include_sensitive: bool = False,
        include_full_body: bool = False,
        max_body_chars: int = 4096,
    ) -> TrafficDetailResult:
        cache_key = (source, capture_id or recording_path)
        cached = self._detail_cache.get(cache_key, {})
        entry = cached.get(entry_id)

        if entry is None:
            if source == "history":
                if recording_path:
                    raw_entries = await self.history_service.get_snapshot(recording_path)
                    source_key = recording_path
                else:
                    source_key, raw_entries = await self.history_service.load_latest_with_path()
                self._analyze_entries(
                    source="history",
                    raw_entries=raw_entries,
                    query=TrafficQuery(preset="all_http", max_items=200, scan_limit=2000),
                    recording_path=source_key,
                    cache_all=True,
                )
                cached = self._detail_cache.get(("history", source_key), {})
                entry = cached.get(entry_id)
            elif source == "live":
                if not capture_id:
                    raise ValueError("capture_id is required for live detail lookup")
                live_result = await self.live_service.read(
                    capture_id,
                    cursor=0,
                    limit=500,
                    advance=False,
                )
                self._analyze_entries(
                    source="live",
                    raw_entries=live_result.items,
                    query=TrafficQuery(preset="all_http", max_items=200, scan_limit=2000),
                    capture_id=capture_id,
                    cache_all=True,
                )
                cached = self._detail_cache.get(("live", capture_id), {})
                entry = cached.get(entry_id)
            else:
                raise ValueError("source must be `live` or `history`")

        if entry is None:
            raise ValueError(f"traffic entry `{entry_id}` was not found")

        if include_sensitive or include_full_body:
            if source == "history":
                effective_recording_path = recording_path or entry.recording_path
                if recording_path:
                    raw_entries = await self.history_service.get_snapshot(recording_path)
                else:
                    raw_entries = await self.history_service.load_latest()
                hydrated = self._hydrate_entry(
                    raw_entries,
                    entry_id,
                    source=source,
                    capture_id=capture_id,
                    recording_path=effective_recording_path,
                    include_sensitive=include_sensitive,
                    include_full_body=include_full_body,
                    max_body_chars=max_body_chars,
                )
                if hydrated is not None:
                    entry = hydrated
            elif source == "live":
                if not capture_id:
                    raise ValueError("capture_id is required for live detail lookup")
                live_result = await self.live_service.read(
                    capture_id,
                    cursor=0,
                    limit=500,
                    advance=False,
                )
                hydrated = self._hydrate_entry(
                    live_result.items,
                    entry_id,
                    source=source,
                    capture_id=capture_id,
                    recording_path=recording_path,
                    include_sensitive=include_sensitive,
                    include_full_body=include_full_body,
                    max_body_chars=max_body_chars,
                )
                if hydrated is not None:
                    entry = hydrated

        detail = self.analysis_service.build_detail(
            entry,
            include_sensitive=include_sensitive,
        )
        return TrafficDetailResult(
            source=source,
            entry_id=entry_id,
            detail=detail,
            warnings=[],
        )

    async def get_stats(
        self,
        *,
        source: str,
        capture_id: str | None = None,
        recording_path: str | None = None,
        preset: str = "api_focus",
        scan_limit: int = 500,
    ) -> CaptureAnalysisStatsResult:
        query = TrafficQuery(preset=preset, max_items=1, scan_limit=scan_limit)
        source_key = capture_id if source == "live" else recording_path
        if source == "live":
            if not capture_id:
                raise ValueError("capture_id is required for live stats")
            live_result = await self.live_service.read(
                capture_id,
                cursor=0,
                limit=scan_limit,
                advance=False,
            )
            result = self._analyze_entries(
                source="live",
                raw_entries=live_result.items,
                query=query,
                capture_id=capture_id,
                next_cursor=live_result.next_cursor,
                initial_warnings=list(live_result.warnings),
                include_items=False,
            )
        else:
            if recording_path:
                source_key = recording_path
                raw_entries = await self.history_service.get_snapshot(recording_path)
            else:
                source_key, raw_entries = await self.history_service.load_latest_with_path()
            result = self._analyze_entries(
                source="history",
                raw_entries=raw_entries,
                query=query,
                recording_path=source_key,
                include_items=False,
            )

        return self.analysis_service.build_stats(
            source=source,
            preset=preset,
            total_items=result.total_items,
            scanned_count=result.scanned_count,
            classified_counts=self._classified_cache.get(
                (source, source_key),
                {},
            ),
            warnings=result.warnings,
        )

    async def group_capture(
        self,
        *,
        source: str,
        group_by: TrafficGroupBy,
        query: TrafficQuery,
        capture_id: str | None = None,
        recording_path: str | None = None,
        max_groups: int = 10,
    ) -> CaptureAnalysisGroupsResult:
        source_key = capture_id if source == "live" else recording_path
        if source == "live":
            if not capture_id:
                raise ValueError("capture_id is required for live grouped analysis")
            live_result = await self.live_service.read(
                capture_id,
                cursor=0,
                limit=query.scan_limit,
                advance=False,
            )
            prepared = self._prepare_entries(
                source="live",
                raw_entries=live_result.items,
                query=query,
                capture_id=capture_id,
                next_cursor=live_result.next_cursor,
                initial_warnings=list(live_result.warnings),
            )
        elif source == "history":
            if recording_path:
                source_key = recording_path
                raw_entries = await self.history_service.get_snapshot(recording_path)
            else:
                source_key, raw_entries = await self.history_service.load_latest_with_path()
            prepared = self._prepare_entries(
                source="history",
                raw_entries=raw_entries,
                query=query,
                recording_path=source_key,
            )
        else:
            raise ValueError("source must be `live` or `history`")

        groups: dict[str, dict] = {}
        for entry, _ in prepared.matched_entries:
            group_value = self._group_value(entry, group_by)
            bucket = groups.setdefault(
                group_value,
                {
                    "group_value": group_value,
                    "count": 0,
                    "total_size": 0,
                    "has_error_count": 0,
                    "sample_paths": [],
                    "sample_entry_ids": [],
                    "resource_classes": set(),
                },
            )
            bucket["count"] += 1
            bucket["total_size"] += entry.total_size or 0
            bucket["has_error_count"] += 1 if (entry.response_status or 0) >= 400 or entry.error_message else 0
            if entry.path and entry.path not in bucket["sample_paths"] and len(bucket["sample_paths"]) < 3:
                bucket["sample_paths"].append(entry.path)
            if entry.entry_id not in bucket["sample_entry_ids"] and len(bucket["sample_entry_ids"]) < 3:
                bucket["sample_entry_ids"].append(entry.entry_id)
            bucket["resource_classes"].add(entry.resource_class)

        ordered_groups = sorted(
            groups.values(),
            key=lambda item: (item["count"], item["total_size"], item["group_value"]),
            reverse=True,
        )

        return CaptureAnalysisGroupsResult(
            source=source,
            group_by=group_by,
            groups=[
                TrafficGroupSummary(
                    group_value=item["group_value"],
                    count=item["count"],
                    total_size=item["total_size"],
                    has_error_count=item["has_error_count"],
                    sample_paths=item["sample_paths"],
                    sample_entry_ids=item["sample_entry_ids"],
                    resource_classes=sorted(item["resource_classes"]),
                )
                for item in ordered_groups[:max_groups]
            ],
            total_items=prepared.total_items,
            scanned_count=prepared.scanned_count,
            matched_count=prepared.matched_count,
            filtered_out_count=prepared.filtered_out_count,
            filtered_out_by_class=prepared.filtered_out_by_class,
            truncated=prepared.truncated or len(ordered_groups) > max_groups,
            warnings=prepared.warnings,
        )

    def _analyze_entries(
        self,
        *,
        source: str,
        raw_entries: list[dict],
        query: TrafficQuery,
        capture_id: str | None = None,
        recording_path: str | None = None,
        next_cursor: int | None = None,
        initial_warnings: list[str] | None = None,
        cache_all: bool = False,
        include_items: bool = True,
    ) -> TrafficQueryResult:
        prepared = self._prepare_entries(
            source=source,
            raw_entries=raw_entries,
            query=query,
            capture_id=capture_id,
            recording_path=recording_path,
            next_cursor=next_cursor,
            initial_warnings=initial_warnings,
            cache_all=cache_all,
        )
        matched_entries = list(prepared.matched_entries)
        matched_entries.sort(key=self._summary_sort_key, reverse=True)
        if include_items:
            matched_summaries = [
                self.analysis_service.summarize_entry(
                    entry,
                    match,
                    max_headers_per_side=query.max_headers_per_side,
                    include_body_preview=query.include_body_preview,
                )
                for entry, match in matched_entries[: query.max_items]
            ]
        else:
            matched_summaries = []

        truncated = prepared.truncated
        if include_items and len(matched_entries) > query.max_items:
            truncated = True

        return TrafficQueryResult(
            source=source,
            items=matched_summaries if include_items else [],
            total_items=prepared.total_items,
            scanned_count=prepared.scanned_count,
            matched_count=prepared.matched_count,
            filtered_out_count=prepared.filtered_out_count,
            filtered_out_by_class=prepared.filtered_out_by_class,
            next_cursor=prepared.next_cursor,
            truncated=truncated,
            warnings=prepared.warnings,
        )

    def _prepare_entries(
        self,
        *,
        source: str,
        raw_entries: list[dict],
        query: TrafficQuery,
        capture_id: str | None = None,
        recording_path: str | None = None,
        next_cursor: int | None = None,
        initial_warnings: list[str] | None = None,
        cache_all: bool = False,
    ):
        warnings = list(initial_warnings or [])
        total_items = len(raw_entries)
        scanned_entries = raw_entries[: query.scan_limit]
        truncated = total_items > query.scan_limit
        if truncated:
            warnings.append("scan_limit_reached")

        filtered_out_by_class: Counter[str] = Counter()
        classified_counts: Counter[str] = Counter()
        matched_entries: list[tuple[TrafficEntry, object]] = []
        detail_entries: dict[str, TrafficEntry] = {}
        matched_entry_ids: set[str] = set()

        for raw in scanned_entries:
            if not isinstance(raw, dict):
                continue
            classification = classify_entry(raw)
            classified_counts[classification.resource_class] += 1

            if self._excluded_by_preset(classification.resource_class, query):
                filtered_out_by_class[classification.resource_class] += 1
                continue

            entry = self.normalizer.normalize_entry(
                raw,
                capture_source=source,
                capture_id=capture_id,
                recording_path=recording_path,
                include_sensitive=query.include_sensitive,
                include_full_body=False,
                max_preview_chars=query.max_preview_chars,
                max_headers_per_side=query.max_headers_per_side,
            )
            detail_entries[entry.entry_id] = entry
            match = self.analysis_service.match_entry(entry, query)
            if not match.matched:
                continue
            matched_entry_ids.add(entry.entry_id)
            matched_entries.append((entry, match))

        cache_scope = capture_id if source == "live" else recording_path
        if cache_scope is not None or cache_all:
            self._detail_cache[(source, cache_scope)] = detail_entries
            self._classified_cache[(source, cache_scope)] = dict(classified_counts)

        return _PreparedTrafficEntries(
            total_items=total_items,
            scanned_count=len(scanned_entries),
            matched_count=len(matched_entry_ids),
            filtered_out_count=sum(filtered_out_by_class.values()),
            filtered_out_by_class=dict(filtered_out_by_class),
            classified_counts=dict(classified_counts),
            matched_entries=matched_entries,
            next_cursor=next_cursor,
            truncated=truncated,
            warnings=warnings,
        )

    def _hydrate_entry(
        self,
        raw_entries: list[dict],
        entry_id: str,
        *,
        source: str,
        capture_id: str | None,
        recording_path: str | None,
        include_sensitive: bool,
        include_full_body: bool,
        max_body_chars: int,
    ) -> TrafficEntry | None:
        for raw in raw_entries:
            if not isinstance(raw, dict):
                continue
            hydrated = self.normalizer.normalize_entry(
                raw,
                capture_source=source,
                capture_id=capture_id,
                recording_path=recording_path,
                include_sensitive=include_sensitive,
                include_full_body=include_full_body,
                max_preview_chars=min(max_body_chars, 1024),
                max_headers_per_side=32,
                max_full_body_chars=max_body_chars,
            )
            if hydrated.entry_id == entry_id:
                return hydrated
        return None

    @staticmethod
    def _excluded_by_preset(resource_class: str, query: TrafficQuery) -> bool:
        if query.preset == "all_http":
            return resource_class == "control"
        if query.preset == "errors_only":
            return resource_class in {"control", "static_asset", "font", "media", "connect_tunnel"}
        if query.preset == "page_bootstrap":
            return resource_class in {"control", "static_asset", "font", "media", "connect_tunnel"}
        return resource_class in {"control", "static_asset", "font", "media", "connect_tunnel"}

    @staticmethod
    def _summary_sort_key(item: tuple[TrafficEntry, object]) -> tuple[int, int, str]:
        entry, _ = item
        start_time = str((entry.times or {}).get("start") or "")
        error_rank = 1 if (entry.response_status or 0) >= 400 or entry.error_message else 0
        return (entry.priority_score, error_rank, start_time)

    @staticmethod
    def _group_value(entry: TrafficEntry, group_by: TrafficGroupBy) -> str:
        if group_by == "host_path":
            host = entry.host or "unknown"
            path = entry.path or "unknown"
            return f"{host} {path}"
        if group_by == "host_status":
            host = entry.host or "unknown"
            status = str(entry.response_status or "unknown")
            return f"{host} {status}"
        if group_by == "response_status":
            return str(entry.response_status or "unknown")
        value = getattr(entry, group_by, None)
        return str(value or "unknown")


class _PreparedTrafficEntries:
    """Internal prepared analysis payload reused by query and grouping paths."""

    def __init__(
        self,
        *,
        total_items: int,
        scanned_count: int,
        matched_count: int,
        filtered_out_count: int,
        filtered_out_by_class: dict[str, int],
        classified_counts: dict[str, int],
        matched_entries: list[tuple[TrafficEntry, object]],
        next_cursor: int | None,
        truncated: bool,
        warnings: list[str],
    ) -> None:
        self.total_items = total_items
        self.scanned_count = scanned_count
        self.matched_count = matched_count
        self.filtered_out_count = filtered_out_count
        self.filtered_out_by_class = filtered_out_by_class
        self.classified_counts = classified_counts
        self.matched_entries = matched_entries
        self.next_cursor = next_cursor
        self.truncated = truncated
        self.warnings = warnings
