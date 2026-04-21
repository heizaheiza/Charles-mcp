from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from charles_mcp.schemas.analysis import (
    CaptureAnalysisGroupsResult,
    CaptureAnalysisStatsResult,
    TrafficDetailResult,
    TrafficGroupBy,
    TrafficQueryResult,
)
from charles_mcp.schemas.history import (
    RecordedTrafficQueryResult,
    RecordingListResult,
    RecordingSnapshotResult,
)
from charles_mcp.schemas.traffic import CaptureSource
from charles_mcp.schemas.traffic_query import TrafficPreset
from charles_mcp.tools.tool_contract import (
    HostContains,
    HttpMethodFilter,
    KeywordRegex,
    ToolContext,
    build_tool_guidance_error,
    build_traffic_query,
    get_tool_dependencies,
    guidance_error_message,
    normalize_http_method,
    normalize_text_filter,
)


def register_history_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def analyze_recorded_traffic(
        ctx: ToolContext,
        recording_path: Optional[str] = None,
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
        """Analyze a saved recording snapshot with compact summaries.
        This is a history-plane tool; preserve recording_path for follow-up detail calls.
        Returns structured TrafficSummary items with matched_fields and match_reasons.
        Use get_traffic_entry_detail to drill down into a specific entry_id afterwards."""
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
        return await deps.traffic_query_service.analyze_recorded_traffic(
            recording_path=recording_path,
            query=query,
        )

    @mcp.tool()
    async def get_traffic_entry_detail(
        ctx: ToolContext,
        source: CaptureSource,
        entry_id: str,
        capture_id: Optional[str] = None,
        recording_path: Optional[str] = None,
        include_full_body: bool = False,
        max_body_chars: int = 2048,
    ) -> TrafficDetailResult:
        """Load one traffic entry detail view for drill-down inspection.
        Requires entry_id from a prior summary/query call.
        Use detail for one confirmed target, not bulk browsing.
        For history entries, pass recording_path from the summary.
        For live entries, pass capture_id from the summary.
        Keep include_full_body=false unless you specifically need the raw body text."""
        deps = get_tool_dependencies(ctx)
        return await deps.traffic_query_service.get_detail(
            source=source,
            entry_id=entry_id,
            capture_id=capture_id,
            recording_path=recording_path,
            include_full_body=include_full_body,
            max_body_chars=max_body_chars,
        )

    @mcp.tool()
    async def get_capture_analysis_stats(
        ctx: ToolContext,
        source: CaptureSource,
        capture_id: Optional[str] = None,
        recording_path: Optional[str] = None,
        preset: TrafficPreset = "api_focus",
        scan_limit: int = 500,
    ) -> CaptureAnalysisStatsResult:
        """Return coarse traffic class counts for a live capture or saved recording."""
        deps = get_tool_dependencies(ctx)
        return await deps.traffic_query_service.get_stats(
            source=source,
            capture_id=capture_id,
            recording_path=recording_path,
            preset=preset,
            scan_limit=scan_limit,
        )

    @mcp.tool()
    async def group_capture_analysis(
        ctx: ToolContext,
        source: CaptureSource,
        group_by: TrafficGroupBy,
        capture_id: Optional[str] = None,
        recording_path: Optional[str] = None,
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
        max_groups: int = 10,
        max_preview_chars: int = 128,
        max_headers_per_side: int = 6,
        scan_limit: int = 500,
    ) -> CaptureAnalysisGroupsResult:
        """Group analyzed traffic so the agent can inspect hot spots with lower token cost."""
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
            include_body_preview=False,
            max_items=max_groups,
            max_preview_chars=max_preview_chars,
            max_headers_per_side=max_headers_per_side,
            scan_limit=scan_limit,
        )
        return await deps.traffic_query_service.group_capture(
            source=source,
            group_by=group_by,
            capture_id=capture_id,
            recording_path=recording_path,
            query=query,
            max_groups=max_groups,
        )

    @mcp.tool()
    async def query_recorded_traffic(
        ctx: ToolContext,
        host_contains: HostContains = None,
        http_method: HttpMethodFilter = None,
        keyword_regex: KeywordRegex = None,
        keep_request: bool = True,
        keep_response: bool = True,
    ) -> RecordedTrafficQueryResult:
        """Query the latest saved recording. This tool never reads the live Charles session."""
        deps = get_tool_dependencies(ctx)
        host_contains_normalized = normalize_text_filter(host_contains)
        method_normalized, method_error = normalize_http_method(http_method)
        if method_error:
            raise ValueError(guidance_error_message(method_error))

        if keyword_regex:
            valid, error_msg = deps.history_service.validate_keyword_regex(keyword_regex)
            if not valid:
                raise ValueError(
                    guidance_error_message(
                        build_tool_guidance_error(
                            parameter="keyword_regex",
                            received=keyword_regex,
                            reason=f"invalid regex: {error_msg}",
                            valid_input="Provide a valid Python regular expression.",
                            retry_example='query_recorded_traffic(keyword_regex="token|session")',
                        )
                    )
                )

        return await deps.history_service.query_latest_result(
            host_contains=host_contains_normalized,
            method_normalized=method_normalized,
            keyword_regex=keyword_regex,
            keep_request=keep_request,
            keep_response=keep_response,
        )

    @mcp.tool()
    async def list_recordings(ctx: ToolContext) -> RecordingListResult:
        """List saved recording files using an explicit history-oriented tool name.
        Start history analysis here, then preserve recording_path for summary/detail calls."""
        deps = get_tool_dependencies(ctx)
        return deps.history_service.list_recordings_result()

    @mcp.tool()
    async def get_recording_snapshot(
        ctx: ToolContext,
        path: Optional[str] = None,
    ) -> RecordingSnapshotResult:
        """Load a saved recording snapshot. This tool never reads the live Charles session."""
        deps = get_tool_dependencies(ctx)
        try:
            return await deps.history_service.get_snapshot_result(path)
        except Exception as exc:
            raise ValueError(str(exc)) from exc
