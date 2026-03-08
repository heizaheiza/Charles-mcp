"""Schemas for normalized HTTP traffic entries."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CaptureSource = Literal["live", "history"]
ResourceClass = Literal[
    "api_candidate",
    "document",
    "script",
    "static_asset",
    "media",
    "font",
    "connect_tunnel",
    "control",
    "unknown",
]
BodyKind = Literal["none", "json", "form", "multipart", "text", "binary", "base64", "unknown"]


class ResourceClassification(BaseModel):
    resource_class: ResourceClass
    priority_score: int = 0
    priority_reasons: list[str] = Field(default_factory=list)


class HeaderKV(BaseModel):
    name: str
    value: str | None
    lower_name: str
    redacted: bool = Field(
        default=False,
        description="Deprecated compatibility field. Traffic is no longer redacted.",
    )


class BodyContent(BaseModel):
    kind: BodyKind = "none"
    mime_type: str | None = None
    charset: str | None = None
    content_encoding: str | None = None
    size_bytes: int | None = None
    preview_text: str | None = None
    preview_truncated: bool = False
    full_text: str | None = None
    full_text_truncated: bool = False
    parsed_json: dict[str, Any] | list[Any] | None = None
    parsed_form: dict[str, list[str]] | None = None
    multipart_summary: list[dict[str, Any]] = Field(default_factory=list)
    decode_warnings: list[str] = Field(default_factory=list)
    redactions_applied: list[str] = Field(
        default_factory=list,
        description="Deprecated compatibility field. Always empty.",
    )


class HttpMessage(BaseModel):
    first_line: str | None = None
    headers: list[HeaderKV] = Field(default_factory=list)
    header_map: dict[str, list[str]] = Field(default_factory=dict)
    mime_type: str | None = None
    charset: str | None = None
    content_encoding: str | None = None
    body: BodyContent = Field(default_factory=BodyContent)
    redactions_applied: list[str] = Field(
        default_factory=list,
        description="Deprecated compatibility field. Always empty.",
    )


class TrafficEntry(BaseModel):
    entry_id: str
    capture_source: CaptureSource
    capture_id: str | None = None
    recording_path: str | None = None
    resource_class: ResourceClass
    priority_score: int
    priority_reasons: list[str] = Field(default_factory=list)
    method: str | None = None
    scheme: str | None = None
    host: str | None = None
    path: str | None = None
    query: str | None = None
    response_status: int | None = None
    status: str | None = None
    total_size: int | None = None
    error_message: str | None = None
    notes: str | None = None
    times: dict[str, Any] = Field(default_factory=dict)
    durations: dict[str, Any] = Field(default_factory=dict)
    request: HttpMessage = Field(default_factory=HttpMessage)
    response: HttpMessage = Field(default_factory=HttpMessage)


class TrafficMatch(BaseModel):
    matched: bool
    matched_fields: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)


class TrafficSummary(BaseModel):
    entry_id: str
    capture_source: CaptureSource
    capture_id: str | None = None
    recording_path: str | None = None
    resource_class: ResourceClass
    priority_score: int
    method: str | None = None
    host: str | None = None
    path: str | None = None
    response_status: int | None = None
    request_content_type: str | None = None
    response_content_type: str | None = None
    total_size: int | None = None
    has_error: bool = False
    error_message: str | None = None
    request_header_highlights: dict[str, str] = Field(default_factory=dict)
    response_header_highlights: dict[str, str] = Field(default_factory=dict)
    request_body_preview: str | None = None
    response_body_preview: str | None = None
    preview_truncated: bool = False
    matched_fields: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    redactions_applied: list[str] = Field(
        default_factory=list,
        description="Deprecated compatibility field. Always empty.",
    )
    detail_available: bool = True


class TrafficDetail(BaseModel):
    entry: TrafficEntry
    raw_body_included: bool = False
    sensitive_included: bool = Field(
        default=False,
        description="Deprecated compatibility field. Traffic is always returned in full.",
    )
    body_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
