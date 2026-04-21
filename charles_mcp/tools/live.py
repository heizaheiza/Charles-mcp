from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from charles_mcp.schemas.analysis import TrafficQueryResult
from charles_mcp.schemas.live_capture import (
    LiveCaptureReadResult,
    LiveCaptureStartResult,
    StopLiveCaptureResult,
)
from charles_mcp.schemas.traffic_query import TrafficPreset
from charles_mcp.tools.tool_contract import ToolContext, build_traffic_query, get_tool_dependencies

_ENTRY_SUMMARY_KEYS = (
    "method", "scheme", "host", "path", "query", "status",
    "totalSize", "errorMessage",
)
_MAX_BODY_PREVIEW_CHARS = 256


def _summarize_raw_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Compact a raw Charles entry to routing fields only, preventing context explosion."""
    summary: dict[str, Any] = {}
    for key in _ENTRY_SUMMARY_KEYS:
        value = entry.get(key)
        if value is not None:
            summary[key] = value

    response = entry.get("response")
    if isinstance(response, dict):
        resp_status = response.get("status")
        if resp_status is not None:
            summary["response_status"] = resp_status
        resp_mime = response.get("mimeType")
        if resp_mime:
            summary["response_content_type"] = resp_mime

    request = entry.get("request")
    if isinstance(request, dict):
        req_mime = request.get("mimeType")
        if req_mime:
            summary["request_content_type"] = req_mime

    times = entry.get("times")
    if isinstance(times, dict) and times.get("start"):
        summary["start_time"] = times["start"]

    return summary


def _compact_read_result(result: LiveCaptureReadResult) -> LiveCaptureReadResult:
    """Replace raw items with compact summaries to avoid token explosion."""
    compacted = [_summarize_raw_entry(item) for item in result.items if isinstance(item, dict)]
    return result.model_copy(update={"items": compacted})


def register_live_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def start_live_capture(
        ctx: ToolContext,
        reset_session: bool = True,
        include_existing: bool = False,
        adopt_existing: bool = False,
    ) -> LiveCaptureStartResult:
        """Start or adopt a live capture session for incremental polling.
        Returns a capture_id required by all other live tools.
        Preserve and reuse capture_id across follow-up live calls.
        Use adopt_existing=true to take over an ongoing Charles session without clearing it."""
        deps = get_tool_dependencies(ctx)
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
        ctx: ToolContext,
        capture_id: str,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> LiveCaptureReadResult:
        """Read incremental traffic and advance the cursor.
        Returns compact entry summaries (host/method/path/status only).
        This read call consumes the current increment.
        Use query_live_capture_entries for structured filtering instead of this tool.
        This tool advances the internal cursor — repeated calls only return new items."""
        deps = get_tool_dependencies(ctx)
        try:
            result = await deps.live_service.read(
                capture_id,
                cursor=cursor,
                limit=limit,
            )
            return _compact_read_result(result)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    async def peek_live_capture(
        ctx: ToolContext,
        capture_id: str,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> LiveCaptureReadResult:
        """Preview incremental traffic without advancing the cursor.
        Returns compact entry summaries (host/method/path/status only).
        This peek call does not consume the current increment.
        Safe to call repeatedly — does not consume items.
        Use query_live_capture_entries for structured filtering and analysis."""
        deps = get_tool_dependencies(ctx)
        try:
            result = await deps.live_service.read(
                capture_id,
                cursor=cursor,
                limit=limit,
                advance=False,
            )
            return _compact_read_result(result)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    async def stop_live_capture(
        ctx: ToolContext,
        capture_id: str,
        persist: bool = True,
    ) -> StopLiveCaptureResult:
        """Stop an active live capture and optionally persist the filtered snapshot.
        Only status='stopped' means the capture is fully closed."""
        deps = get_tool_dependencies(ctx)
        try:
            return await deps.live_service.stop(capture_id, persist=persist)
        except Exception as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    async def query_live_capture_entries(
        ctx: ToolContext,
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
        include_body_preview: bool = True,
        max_items: int = 10,
        max_preview_chars: int = 128,
        max_headers_per_side: int = 6,
        scan_limit: int = 500,
    ) -> TrafficQueryResult:
        """Analyze the active live capture with structured summary-first filtering.
        This is the RECOMMENDED tool for inspecting live traffic.
        Use this summary path before calling get_traffic_entry_detail.
        Does NOT advance the cursor — safe to call repeatedly with different filters.
        Default cursor=0 scans all captured data from the beginning.
        Use get_traffic_entry_detail to drill down into a specific entry_id."""
        deps = get_tool_dependencies(ctx)
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
