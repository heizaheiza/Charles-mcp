from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from charles_mcp.tools.tool_contract import (
    HostContains,
    HttpMethodFilter,
    KeywordRegex,
    RecordSeconds,
    ToolContext,
    build_tool_guidance_error,
    get_proxy_data,
    get_tool_dependencies,
    normalize_http_method,
    normalize_text_filter,
    seconds_input_error,
)
from charles_mcp.utils import validate_regex

logger = logging.getLogger(__name__)


def register_legacy_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def proxy_by_time(record_seconds: RecordSeconds, ctx: ToolContext) -> list[dict]:
        """Deprecated compatibility alias. Prefer canonical live/history/reverse tools.
        Capture traffic for a fixed duration or read the latest saved history package."""
        logger.info("Tool called: proxy_by_time(record_seconds=%s)", record_seconds)
        deps = get_tool_dependencies(ctx)

        error_payload = seconds_input_error(
            parameter="record_seconds",
            value=record_seconds,
            max_allowed=deps.config.max_stoptime,
            retry_example="proxy_by_time(record_seconds=30)",
        )
        if error_payload:
            return error_payload

        return await get_proxy_data(record_seconds, ctx, deps=deps)

    @mcp.tool()
    async def filter_func(
        capture_seconds: RecordSeconds,
        ctx: ToolContext,
        host_contains: HostContains = None,
        http_method: HttpMethodFilter = None,
        keyword_regex: KeywordRegex = None,
        keep_request: bool = True,
        keep_response: bool = True,
    ) -> list[dict]:
        """Deprecated compatibility alias. Prefer canonical live/history/reverse tools.
        Filter traffic from a fixed capture window or the latest saved history package."""
        logger.info(
            "Tool called: filter_func(capture_seconds=%s, host_contains=%s, http_method=%s)",
            capture_seconds,
            host_contains,
            http_method,
        )
        deps = get_tool_dependencies(ctx)

        error_payload = seconds_input_error(
            parameter="capture_seconds",
            value=capture_seconds,
            max_allowed=deps.config.max_stoptime,
            retry_example='filter_func(capture_seconds=30, host_contains="api.example.com")',
        )
        if error_payload:
            return error_payload

        host_contains_normalized = normalize_text_filter(host_contains)
        method_normalized, method_error = normalize_http_method(http_method)
        if method_error:
            return method_error

        if keyword_regex:
            valid, error_msg = validate_regex(keyword_regex)
            if not valid:
                return build_tool_guidance_error(
                    parameter="keyword_regex",
                    received=keyword_regex,
                    reason=f"invalid regex: {error_msg}",
                    valid_input="Provide a valid Python regular expression.",
                    retry_example='filter_func(capture_seconds=0, keyword_regex="token|session")',
                )

        raw_data = await get_proxy_data(capture_seconds, ctx, deps=deps)
        if not isinstance(raw_data, list):
            return raw_data

        return deps.history_service.filter_entries(
            raw_data,
            host_contains=host_contains_normalized,
            method_normalized=method_normalized,
            keyword_regex=keyword_regex,
            keep_request=keep_request,
            keep_response=keep_response,
        )

    @mcp.tool()
    async def list_sessions(ctx: ToolContext) -> list[dict]:
        """Deprecated compatibility alias. Prefer canonical live/history/reverse tools.
        List historical session files via the legacy tool name."""
        logger.info("Tool called: list_sessions()")
        deps = get_tool_dependencies(ctx)

        recordings = deps.history_service.list_recordings_result()
        if not recordings.items:
            return [{"message": "No recordings available"}]
        return [item.model_dump() for item in recordings.items]
