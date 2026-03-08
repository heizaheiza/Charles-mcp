"""Schemas for traffic analysis queries."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from charles_mcp.schemas.traffic import ResourceClass

TrafficPreset = Literal["api_focus", "errors_only", "all_http", "page_bootstrap"]


class TrafficQuery(BaseModel):
    preset: TrafficPreset = "api_focus"
    host_contains: str | None = None
    path_contains: str | None = None
    method_in: list[str] = Field(default_factory=list)
    status_in: list[int] = Field(default_factory=list)
    has_error: bool | None = None
    resource_class_in: list[ResourceClass] = Field(default_factory=list)
    min_priority_score: int | None = None
    request_header_name: str | None = None
    request_header_value_contains: str | None = None
    response_header_name: str | None = None
    response_header_value_contains: str | None = None
    request_content_type: str | None = None
    response_content_type: str | None = None
    request_body_contains: str | None = None
    response_body_contains: str | None = None
    request_json_query: str | None = None
    response_json_query: str | None = None
    min_total_size: int | None = None
    max_total_size: int | None = None
    include_sensitive: bool = Field(
        default=False,
        description="Deprecated compatibility field. No longer affects returned traffic.",
        deprecated=True,
    )
    include_body_preview: bool = True
    max_items: int = Field(default=20, ge=1, le=200)
    max_preview_chars: int = Field(default=256, ge=32, le=4096)
    max_headers_per_side: int = Field(default=8, ge=1, le=32)
    scan_limit: int = Field(default=500, ge=1, le=5000)
