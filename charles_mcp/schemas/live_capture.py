"""Schemas for live capture tool contracts."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class LiveCaptureStartResult(BaseModel):
    """Start or adopt a live capture session."""

    capture_id: str
    status: Literal["active"]
    managed: bool
    include_existing: bool
    warnings: list[str] = Field(default_factory=list)


class LiveCaptureReadResult(BaseModel):
    """Incremental live capture read result."""

    capture_id: str
    status: Literal["active", "reset_detected", "stopped"]
    items: list[dict[str, Any]]
    next_cursor: int
    total_new_items: int
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class StopLiveCaptureResult(BaseModel):
    """Stop a live capture session."""

    capture_id: str
    status: Literal["stopped", "stop_failed"]
    persisted_path: str | None = None
    total_items: int
    recoverable: bool = False
    active_capture_preserved: bool = False
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
