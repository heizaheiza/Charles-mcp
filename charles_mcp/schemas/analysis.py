"""Schemas for traffic analysis tool outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

from charles_mcp.schemas.traffic import CaptureSource, ResourceClass, TrafficDetail, TrafficSummary

TrafficGroupBy = Literal[
    "host",
    "path",
    "response_status",
    "resource_class",
    "method",
    "host_path",
    "host_status",
]


def _strip_none(data: Any) -> Any:
    """Recursively remove None values from serialized output."""
    if isinstance(data, dict):
        return {k: _strip_none(v) for k, v in data.items() if v is not None}
    if isinstance(data, list):
        return [_strip_none(item) for item in data]
    return data


class TrafficQueryResult(BaseModel):
    source: CaptureSource
    items: list[TrafficSummary] = Field(default_factory=list)
    total_items: int = 0
    scanned_count: int = 0
    matched_count: int = 0
    filtered_out_count: int = 0
    filtered_out_by_class: dict[ResourceClass, int] = Field(default_factory=dict)
    next_cursor: int | None = None
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _compact(self, handler: Any) -> Any:
        return _strip_none(handler(self))


class TrafficDetailResult(BaseModel):
    source: CaptureSource
    entry_id: str
    detail: TrafficDetail
    warnings: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _compact(self, handler: Any) -> Any:
        return _strip_none(handler(self))


class CaptureAnalysisStatsResult(BaseModel):
    source: CaptureSource
    total_items: int = 0
    scanned_count: int = 0
    classified_counts: dict[ResourceClass, int] = Field(default_factory=dict)
    preset: str
    warnings: list[str] = Field(default_factory=list)


class TrafficGroupSummary(BaseModel):
    group_value: str
    count: int = 0
    total_size: int = 0
    has_error_count: int = 0
    sample_paths: list[str] = Field(default_factory=list)
    sample_entry_ids: list[str] = Field(default_factory=list)
    resource_classes: list[ResourceClass] = Field(default_factory=list)


class CaptureAnalysisGroupsResult(BaseModel):
    source: CaptureSource
    group_by: TrafficGroupBy
    groups: list[TrafficGroupSummary] = Field(default_factory=list)
    total_items: int = 0
    scanned_count: int = 0
    matched_count: int = 0
    filtered_out_count: int = 0
    filtered_out_by_class: dict[ResourceClass, int] = Field(default_factory=dict)
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
