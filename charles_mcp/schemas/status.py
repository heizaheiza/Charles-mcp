"""Schemas for Charles status and runtime observability."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CharlesStatusConfig(BaseModel):
    """Static configuration details relevant to the MCP runtime."""

    proxy_url: str
    base_url: str
    config_path: str
    manage_charles_lifecycle: bool


class ActiveCaptureStatus(BaseModel):
    """Snapshot of the active live capture state."""

    capture_id: str
    status: str
    managed: bool
    include_existing: bool
    cursor: int
    started_at: str
    warnings: list[str]


class LiveCaptureRuntimeStatus(BaseModel):
    """Top-level live capture runtime view."""

    active_capture: ActiveCaptureStatus | None = None


class CharlesStatusResult(BaseModel):
    """Structured status result for the Charles MCP server."""

    config: CharlesStatusConfig
    live_capture: LiveCaptureRuntimeStatus
    connected: bool
    charles_info: dict[str, Any] | None = None
    error: str | None = None
