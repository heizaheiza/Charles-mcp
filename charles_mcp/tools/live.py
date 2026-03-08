from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from charles_mcp.schemas.analysis import TrafficQueryResult
from charles_mcp.schemas.live_capture import (
    LiveCaptureReadResult,
    LiveCaptureStartResult,
    StopLiveCaptureResult,
)
from charles_mcp.schemas.traffic_query import TrafficPreset
from charles_mcp.tools.tool_contract import ToolDependencies, build_traffic_query


def register_live_tools(mcp: FastMCP, *, deps: ToolDependencies) -> None:
    @mcp.tool()
    async def start_live_capture(
        reset_session: bool = True,
        include_existing: bool = False,
        adopt_existing: bool = False,
    ) -> LiveCaptureStartResult:
        """Start or adopt a live capture session for incremental polling."""
        try:
            return await deps.live_service.start(
                reset_session=reset_session,
                include_existing=include_existing,
                adopt_existing=adopt_existing,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    async def read_live_capture(
        capture_id: str,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> LiveCaptureReadResult:
        """Read incremental traffic from the current Charles session without history fallback."""
        try:
            return await deps.live_service.read(
                capture_id,
                cursor=cursor,
                limit=limit,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    async def peek_live_capture(
        capture_id: str,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> LiveCaptureReadResult:
        """Preview incremental traffic without advancing the live cursor."""
        try:
            return await deps.live_service.read(
                capture_id,
                cursor=cursor,
                limit=limit,
                advance=False,
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    async def stop_live_capture(
        capture_id: str,
        persist: bool = True,
    ) -> StopLiveCaptureResult:
        """Stop an active live capture and optionally persist the filtered snapshot."""
        try:
            return await deps.live_service.stop(capture_id, persist=persist)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    async def query_live_capture_entries(
        capture_id: str,
        cursor: Optional[int] = None,
        preset: TrafficPreset = "api_focus",
        host_contains: Optional[str] = None,
        path_contains: Optional[str] = None,
        method_in: Optional[list[str]] = None,
        status_in: Optional[list[int]] = None,
        resource_class_in: Optional[list[str]] = None,
        min_priority_score: Optional[int] = None,
        request_header_name: Optional[str] = None,
        request_header_value_contains: Optional[str] = None,
        response_header_name: Optional[str] = None,
        response_header_value_contains: Optional[str] = None,
        request_content_type: Optional[str] = None,
        response_content_type: Optional[str] = None,
        request_body_contains: Optional[str] = None,
        response_body_contains: Optional[str] = None,
        request_json_query: Optional[str] = None,
        response_json_query: Optional[str] = None,
        include_sensitive: bool = False,
        include_body_preview: bool = True,
        max_items: int = 20,
        max_preview_chars: int = 256,
        max_headers_per_side: int = 8,
        scan_limit: int = 500,
    ) -> TrafficQueryResult:
        """Analyze the active live capture with summary-first filtering."""
        query = build_traffic_query(
            preset=preset,
            host_contains=host_contains,
            path_contains=path_contains,
            method_in=method_in,
            status_in=status_in,
            resource_class_in=resource_class_in,
            min_priority_score=min_priority_score,
            request_header_name=request_header_name,
            request_header_value_contains=request_header_value_contains,
            response_header_name=response_header_name,
            response_header_value_contains=response_header_value_contains,
            request_content_type=request_content_type,
            response_content_type=response_content_type,
            request_body_contains=request_body_contains,
            response_body_contains=response_body_contains,
            request_json_query=request_json_query,
            response_json_query=response_json_query,
            include_sensitive=include_sensitive,
            include_body_preview=include_body_preview,
            max_items=max_items,
            max_preview_chars=max_preview_chars,
            max_headers_per_side=max_headers_per_side,
            scan_limit=scan_limit,
        )
        return await deps.traffic_query_service.analyze_live_capture(
            capture_id=capture_id,
            query=query,
            cursor=cursor,
        )
