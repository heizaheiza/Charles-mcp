from __future__ import annotations

from dataclasses import dataclass

from charles_mcp.schemas.traffic import TrafficEntry, TrafficMatch


@dataclass
class PreparedTrafficEntries:
    """Prepared traffic payload reused across query, stats, and grouping flows."""

    source: str
    identity: str | None
    total_items: int
    scanned_count: int
    matched_count: int
    filtered_out_count: int
    filtered_out_by_class: dict[str, int]
    matched_entries: list[tuple[TrafficEntry, TrafficMatch]]
    next_cursor: int | None
    truncated: bool
    warnings: list[str]
