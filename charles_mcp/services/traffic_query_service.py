from __future__ import annotations

from charles_mcp.schemas.analysis import (
    CaptureAnalysisGroupsResult,
    CaptureAnalysisStatsResult,
    TrafficDetailResult,
    TrafficGroupBy,
    TrafficQueryResult,
)
from charles_mcp.schemas.traffic import CaptureSource
from charles_mcp.schemas.traffic_query import TrafficPreset, TrafficQuery
from charles_mcp.services.history_capture import RecordingHistoryService
from charles_mcp.services.live_capture import LiveCaptureService
from charles_mcp.services.traffic_analysis import TrafficAnalysisService
from charles_mcp.services.traffic_cache import TrafficEntryCache
from charles_mcp.services.traffic_grouping_service import TrafficGroupingService
from charles_mcp.services.traffic_normalizer import TrafficNormalizer
from charles_mcp.services.traffic_query_orchestrator import TrafficQueryOrchestrator
from charles_mcp.services.traffic_stats_service import TrafficStatsService


class TrafficQueryService:
    """Facade that preserves the public query API while delegating to smaller components."""

    def __init__(
        self,
        *,
        live_service: LiveCaptureService,
        history_service: RecordingHistoryService,
        normalizer: TrafficNormalizer,
        analysis_service: TrafficAnalysisService,
        entry_cache: TrafficEntryCache | None = None,
        orchestrator: TrafficQueryOrchestrator | None = None,
        stats_service: TrafficStatsService | None = None,
        grouping_service: TrafficGroupingService | None = None,
    ) -> None:
        self.live_service = live_service
        self.history_service = history_service
        self.normalizer = normalizer
        self.analysis_service = analysis_service
        self.entry_cache = entry_cache or TrafficEntryCache()
        self.orchestrator = orchestrator or TrafficQueryOrchestrator(
            live_service=live_service,
            history_service=history_service,
            normalizer=normalizer,
            analysis_service=analysis_service,
            entry_cache=self.entry_cache,
        )
        self.stats_service = stats_service or TrafficStatsService(
            analysis_service=analysis_service,
            entry_cache=self.entry_cache,
        )
        self.grouping_service = grouping_service or TrafficGroupingService()

    async def analyze_live_capture(
        self,
        *,
        capture_id: str,
        query: TrafficQuery,
        cursor: int | None = None,
    ) -> TrafficQueryResult:
        return await self.orchestrator.analyze_live_capture(
            capture_id=capture_id,
            query=query,
            cursor=cursor,
        )

    async def analyze_recorded_traffic(
        self,
        *,
        recording_path: str | None,
        query: TrafficQuery,
    ) -> TrafficQueryResult:
        return await self.orchestrator.analyze_recorded_traffic(
            recording_path=recording_path,
            query=query,
        )

    async def get_detail(
        self,
        *,
        source: CaptureSource,
        entry_id: str,
        capture_id: str | None = None,
        recording_path: str | None = None,
        include_full_body: bool = False,
        max_body_chars: int = 4096,
    ) -> TrafficDetailResult:
        return await self.orchestrator.get_detail(
            source=source,
            entry_id=entry_id,
            capture_id=capture_id,
            recording_path=recording_path,
            include_full_body=include_full_body,
            max_body_chars=max_body_chars,
        )

    async def get_stats(
        self,
        *,
        source: CaptureSource,
        capture_id: str | None = None,
        recording_path: str | None = None,
        preset: TrafficPreset = "api_focus",
        scan_limit: int = 500,
    ) -> CaptureAnalysisStatsResult:
        prepared = await self.orchestrator.prepare_capture(
            source=source,
            query=TrafficQuery(preset=preset, max_items=1, scan_limit=scan_limit),
            capture_id=capture_id,
            recording_path=recording_path,
            advance=False,
        )
        return self.stats_service.build_result(
            source=source,
            preset=preset,
            prepared=prepared,
        )

    async def group_capture(
        self,
        *,
        source: CaptureSource,
        group_by: TrafficGroupBy,
        query: TrafficQuery,
        capture_id: str | None = None,
        recording_path: str | None = None,
        max_groups: int = 10,
    ) -> CaptureAnalysisGroupsResult:
        prepared = await self.orchestrator.prepare_capture(
            source=source,
            query=query,
            capture_id=capture_id,
            recording_path=recording_path,
            advance=False,
        )
        return self.grouping_service.build_result(
            source=source,
            group_by=group_by,
            prepared=prepared,
            max_groups=max_groups,
        )
