from __future__ import annotations

import logging

from mcp.server.fastmcp import Context, FastMCP

from charles_mcp.tools.tool_contract import (
    HostContains,
    HttpMethodFilter,
    KeywordRegex,
    RecordSeconds,
    ToolDependencies,
    build_tool_guidance_error,
    get_proxy_data,
    normalize_http_method,
    normalize_text_filter,
    seconds_input_error,
)
from charles_mcp.utils import validate_regex

logger = logging.getLogger(__name__)


def register_legacy_tools(mcp: FastMCP, *, deps: ToolDependencies) -> None:
    @mcp.tool()
    async def proxy_by_time(record_seconds: RecordSeconds, ctx: Context) -> list[dict]:
        """抓取或读取 Charles 流量包。"""
        logger.info("Tool called: proxy_by_time(record_seconds=%s)", record_seconds)

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
        ctx: Context,
        host_contains: HostContains = None,
        http_method: HttpMethodFilter = None,
        keyword_regex: KeywordRegex = None,
        keep_request: bool = True,
        keep_response: bool = True,
    ) -> list[dict]:
        """高级过滤与搜索工具。"""
        logger.info(
            "Tool called: filter_func(capture_seconds=%s, host_contains=%s, http_method=%s)",
            capture_seconds,
            host_contains,
            http_method,
        )

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
                    reason=f"无效的正则表达式，{error_msg}",
                    valid_input="请提供简洁且语法正确的 Python 正则表达式。",
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
