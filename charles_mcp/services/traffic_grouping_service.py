from __future__ import annotations

from charles_mcp.schemas.analysis import (
    CaptureAnalysisGroupsResult,
    TrafficGroupBy,
    TrafficGroupSummary,
)
from charles_mcp.schemas.traffic import TrafficEntry
from charles_mcp.services.traffic_query_models import PreparedTrafficEntries


class TrafficGroupingService:
    """Build grouped traffic summaries from prepared query results."""

    def build_result(
        self,
        *,
        source: str,
        group_by: TrafficGroupBy,
        prepared: PreparedTrafficEntries,
        max_groups: int,
    ) -> CaptureAnalysisGroupsResult:
        groups: dict[str, dict] = {}
        for entry, _match in prepared.matched_entries:
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
