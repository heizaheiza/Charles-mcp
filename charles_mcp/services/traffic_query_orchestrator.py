from __future__ import annotations

from collections import Counter

from charles_mcp.analyzers.resource_classifier import classify_entry
from charles_mcp.schemas.analysis import TrafficDetailResult, TrafficQueryResult
from charles_mcp.schemas.traffic import TrafficEntry, TrafficMatch
from charles_mcp.schemas.traffic_query import TrafficQuery
from charles_mcp.services.history_capture import RecordingHistoryService
from charles_mcp.services.live_capture import LiveCaptureService
from charles_mcp.services.traffic_analysis import TrafficAnalysisService
from charles_mcp.services.traffic_cache import SUMMARY_BODY_MODE, TrafficEntryCache
from charles_mcp.services.traffic_normalizer import TrafficNormalizer
from charles_mcp.services.traffic_query_models import PreparedTrafficEntries


class TrafficQueryOrchestrator:
    """Coordinate loading, caching, and summarizing live/history traffic."""

    def __init__(
        self,
        *,
        live_service: LiveCaptureService,
        history_service: RecordingHistoryService,
        normalizer: TrafficNormalizer,
        analysis_service: TrafficAnalysisService,
        entry_cache: TrafficEntryCache,
    ) -> None:
        self.live_service = live_service
        self.history_service = history_service
        self.normalizer = normalizer
        self.analysis_service = analysis_service
        self.entry_cache = entry_cache

    async def analyze_live_capture(
        self,
        *,
        capture_id: str,
        query: TrafficQuery,
        cursor: int | None = None,
    ) -> TrafficQueryResult:
        limit = max(query.max_items * 5, query.max_items, 50)
        prepared = await self.prepare_capture(
            source="live",
            query=query,
            capture_id=capture_id,
            cursor=cursor,
            advance=False,
            read_limit=limit,
        )
        return self.build_query_result(prepared=prepared, query=query, include_items=True)

    async def analyze_recorded_traffic(
        self,
        *,
        recording_path: str | None,
        query: TrafficQuery,
    ) -> TrafficQueryResult:
        try:
            prepared = await self.prepare_capture(
                source="history",
                query=query,
                recording_path=recording_path,
                advance=False,
            )
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
        return self.build_query_result(prepared=prepared, query=query, include_items=True)

    async def prepare_capture(
        self,
        *,
        source: str,
        query: TrafficQuery,
        capture_id: str | None = None,
        recording_path: str | None = None,
        cursor: int | None = None,
        advance: bool = False,
        read_limit: int | None = None,
    ) -> PreparedTrafficEntries:
        if source == "live":
            if not capture_id:
                raise ValueError("capture_id is required for live analysis")
            live_result = await self.live_service.read(
                capture_id,
                cursor=cursor if cursor is not None else 0,
                limit=read_limit or query.scan_limit,
                advance=advance,
            )
            return self._prepare_entries(
                source="live",
                raw_entries=live_result.items,
                query=query,
                capture_id=capture_id,
                next_cursor=live_result.next_cursor,
                initial_warnings=list(live_result.warnings),
            )

        if source == "history":
            source_path, raw_entries = await self._load_history_entries(recording_path)
            return self._prepare_entries(
                source="history",
                raw_entries=raw_entries,
                query=query,
                recording_path=source_path,
            )

        raise ValueError("source must be `live` or `history`")

    def build_query_result(
        self,
        *,
        prepared: PreparedTrafficEntries,
        query: TrafficQuery,
        include_items: bool,
    ) -> TrafficQueryResult:
        matched_entries = list(prepared.matched_entries)
        matched_entries.sort(key=self._summary_sort_key, reverse=True)

        matched_summaries = []
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

        truncated = prepared.truncated
        if include_items and len(matched_entries) > query.max_items:
            truncated = True

        return TrafficQueryResult(
            source=prepared.source,
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

    async def get_detail(
        self,
        *,
        source: str,
        entry_id: str,
        capture_id: str | None = None,
        recording_path: str | None = None,
        include_full_body: bool = False,
        max_body_chars: int = 4096,
    ) -> TrafficDetailResult:
        if source not in {"live", "history"}:
            raise ValueError("source must be `live` or `history`")

        identity = self._resolve_identity(
            source=source,
            entry_id=entry_id,
            capture_id=capture_id,
            recording_path=recording_path,
        )
        body_mode = self._body_mode(include_full_body=include_full_body, max_body_chars=max_body_chars)
        entry = self.entry_cache.get_entry(
            source=source,
            identity=identity,
            entry_id=entry_id,
            body_mode=body_mode,
        )

        if entry is None and body_mode != SUMMARY_BODY_MODE:
            entry = await self._hydrate_and_cache_entry(
                source=source,
                identity=identity,
                entry_id=entry_id,
                max_body_chars=max_body_chars,
            )

        if entry is None:
            await self.cache_summary_scope(source=source, identity=identity)
            entry = self.entry_cache.get_entry(
                source=source,
                identity=identity,
                entry_id=entry_id,
                body_mode=SUMMARY_BODY_MODE,
            )

        if entry is None:
            raise ValueError(f"traffic entry `{entry_id}` was not found in `{identity}`")

        detail = self.analysis_service.build_detail(entry)
        warnings: list[str] = []
        estimated_chars = len(detail.model_dump_json(exclude_none=True))
        if estimated_chars > 12_000:
            warnings.append(
                f"large_response:{estimated_chars}_chars. "
                "Consider using a smaller max_body_chars or include_full_body=false."
            )
        return TrafficDetailResult(
            source=source,
            entry_id=entry_id,
            detail=detail,
            warnings=warnings,
        )

    async def cache_summary_scope(self, *, source: str, identity: str) -> None:
        if source == "history":
            raw_entries = await self.history_service.get_snapshot(identity)
            self._prepare_entries(
                source="history",
                raw_entries=raw_entries,
                query=TrafficQuery(preset="all_http", max_items=200, scan_limit=2000),
                recording_path=identity,
            )
            return

        live_result = await self.live_service.read(
            identity,
            cursor=0,
            limit=500,
            advance=False,
        )
        self._prepare_entries(
            source="live",
            raw_entries=live_result.items,
            query=TrafficQuery(preset="all_http", max_items=200, scan_limit=2000),
            capture_id=identity,
            next_cursor=live_result.next_cursor,
            initial_warnings=list(live_result.warnings),
        )

    async def _hydrate_and_cache_entry(
        self,
        *,
        source: str,
        identity: str,
        entry_id: str,
        max_body_chars: int,
    ) -> TrafficEntry | None:
        if source == "history":
            raw_entries = await self.history_service.get_snapshot(identity)
            capture_id = None
            recording_path = identity
        else:
            live_result = await self.live_service.read(
                identity,
                cursor=0,
                limit=500,
                advance=False,
            )
            raw_entries = live_result.items
            capture_id = identity
            recording_path = None

        for raw in raw_entries:
            if not isinstance(raw, dict):
                continue
            classification = classify_entry(raw)
            hydrated = self.normalizer.normalize_entry(
                raw,
                capture_source=source,
                capture_id=capture_id,
                recording_path=recording_path,
                include_full_body=True,
                max_preview_chars=min(max_body_chars, 1024),
                max_headers_per_side=16,
                max_full_body_chars=max_body_chars,
                classification=classification,
            )
            if hydrated.entry_id != entry_id:
                continue
            self.entry_cache.put(
                source=source,
                identity=identity,
                body_mode=self._body_mode(include_full_body=True, max_body_chars=max_body_chars),
                entries={entry_id: hydrated},
            )
            return hydrated

        return None

    async def _load_history_entries(self, recording_path: str | None) -> tuple[str, list[dict]]:
        if recording_path:
            return recording_path, await self.history_service.get_snapshot(recording_path)
        return await self.history_service.load_latest_with_path()

    def _resolve_identity(
        self,
        *,
        source: str,
        entry_id: str,
        capture_id: str | None,
        recording_path: str | None,
    ) -> str:
        if source == "live":
            if not capture_id:
                raise ValueError("capture_id is required for live detail lookup")
            return capture_id

        if recording_path:
            return recording_path

        resolved = self.entry_cache.resolve_identity(source=source, entry_id=entry_id)
        if resolved is not None:
            return resolved

        raise ValueError(
            "recording_path is required for history detail lookup when the entry is not already cached"
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
    ) -> PreparedTrafficEntries:
        warnings = list(initial_warnings or [])
        total_items = len(raw_entries)
        scanned_entries = raw_entries[: query.scan_limit]
        truncated = total_items > query.scan_limit
        if truncated:
            warnings.append("scan_limit_reached")

        # errors_only preset: inject has_error filter so only error traffic matches
        effective_query = query
        if query.preset == "errors_only" and query.has_error is None:
            effective_query = query.model_copy(update={"has_error": True})

        filtered_out_by_class: Counter[str] = Counter()
        classified_counts: Counter[str] = Counter()
        matched_entries: list[tuple[TrafficEntry, TrafficMatch]] = []
        detail_entries: dict[str, TrafficEntry] = {}

        for raw in scanned_entries:
            if not isinstance(raw, dict):
                continue
            classification = classify_entry(raw)
            classified_counts[classification.resource_class] += 1

            if self._excluded_by_preset(classification.resource_class, effective_query):
                filtered_out_by_class[classification.resource_class] += 1
                continue

            entry = self.normalizer.normalize_entry(
                raw,
                capture_source=source,
                capture_id=capture_id,
                recording_path=recording_path,
                include_full_body=False,
                max_preview_chars=effective_query.max_preview_chars,
                max_headers_per_side=effective_query.max_headers_per_side,
                classification=classification,
            )
            detail_entries[entry.entry_id] = entry
            match = self.analysis_service.match_entry(entry, effective_query)
            if match.matched:
                matched_entries.append((entry, match))

        identity = capture_id if source == "live" else recording_path
        if identity:
            self.entry_cache.put(
                source=source,
                identity=identity,
                body_mode=SUMMARY_BODY_MODE,
                entries=detail_entries,
                classified_counts=dict(classified_counts),
            )

        return PreparedTrafficEntries(
            source=source,
            identity=identity,
            total_items=total_items,
            scanned_count=len(scanned_entries),
            matched_count=len(matched_entries),
            filtered_out_count=sum(filtered_out_by_class.values()),
            filtered_out_by_class=dict(filtered_out_by_class),
            matched_entries=matched_entries,
            next_cursor=next_cursor,
            truncated=truncated,
            warnings=warnings,
        )

    @staticmethod
    def _body_mode(*, include_full_body: bool, max_body_chars: int) -> str:
        if not include_full_body:
            return SUMMARY_BODY_MODE
        return f"full:{max_body_chars}"

    @staticmethod
    def _excluded_by_preset(resource_class: str, query: TrafficQuery) -> bool:
        if query.preset == "all_http":
            return resource_class == "control"
        # api_focus, errors_only, page_bootstrap all exclude the same noise classes
        return resource_class in {"control", "static_asset", "font", "media", "connect_tunnel"}

    @staticmethod
    def _summary_sort_key(item: tuple[TrafficEntry, TrafficMatch]) -> tuple[int, int, str]:
        entry, _ = item
        start_time = str((entry.times or {}).get("start") or "")
        error_rank = 1 if (entry.response_status or 0) >= 400 or entry.error_message else 0
        return (entry.priority_score, error_rank, start_time)
