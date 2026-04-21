from __future__ import annotations

from typing import cast

from charles_mcp.schemas.analysis import CaptureAnalysisStatsResult
from charles_mcp.schemas.traffic import CaptureSource, ResourceClass
from charles_mcp.services.traffic_analysis import TrafficAnalysisService
from charles_mcp.services.traffic_cache import TrafficEntryCache
from charles_mcp.services.traffic_query_models import PreparedTrafficEntries


class TrafficStatsService:
    """Build coarse classified counts from prepared traffic results."""

    def __init__(self, *, analysis_service: TrafficAnalysisService, entry_cache: TrafficEntryCache) -> None:
        self.analysis_service = analysis_service
        self.entry_cache = entry_cache

    def build_result(
        self,
        *,
        source: CaptureSource,
        preset: str,
        prepared: PreparedTrafficEntries,
    ) -> CaptureAnalysisStatsResult:
        classified_counts: dict[ResourceClass, int] = {}
        if prepared.identity:
            classified_counts = cast(
                dict[ResourceClass, int],
                self.entry_cache.get_classified_counts(
                    source=source,
                    identity=prepared.identity,
                ),
            )

        return self.analysis_service.build_stats(
            source=source,
            preset=preset,
            total_items=prepared.total_items,
            scanned_count=prepared.scanned_count,
            classified_counts=classified_counts,
            warnings=prepared.warnings,
        )
