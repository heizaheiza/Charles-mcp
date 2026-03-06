"""
Charles MCP Server 核心模块。

定义所有 MCP 工具、生命周期管理和服务器初始化逻辑。
"""

import os
import json
import signal
import asyncio
import logging
from typing import Annotated, Optional, Any
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

from charles_mcp.config import Config, get_config
from charles_mcp.client import CharlesClient, CharlesClientError
from charles_mcp.schemas.live_capture import (
    LiveCaptureReadResult,
    LiveCaptureStartResult,
    StopLiveCaptureResult,
)
from charles_mcp.schemas.history import (
    RecordedTrafficQueryResult,
    RecordingListResult,
    RecordingSnapshotResult,
)
from charles_mcp.schemas.analysis import (
    CaptureAnalysisGroupsResult,
    CaptureAnalysisStatsResult,
    TrafficGroupBy,
    TrafficDetailResult,
    TrafficQueryResult,
)
from charles_mcp.schemas.traffic_query import TrafficPreset, TrafficQuery
from charles_mcp.schemas.status import (
    ActiveCaptureStatus,
    CharlesStatusConfig,
    CharlesStatusResult,
    LiveCaptureRuntimeStatus,
)
from charles_mcp.services import (
    LiveCaptureService,
    RecordingHistoryService,
    TrafficAnalysisService,
    TrafficNormalizer,
    TrafficQueryService,
)
from charles_mcp.utils import (
    ensure_directory,
    safe_copy_file,
    safe_copy_tree,
    safe_remove_tree,
    validate_regex,
)

logger = logging.getLogger(__name__)

HTTP_METHOD_CHOICES = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
THROTTLING_PRESET_CHOICES = (
    "3G",
    "4G",
    "5G",
    "fibre",
    "100mbps",
    "56k",
    "256k",
    "deactivate",
    "off",
    "on",
    "start",
)

RecordSeconds = Annotated[
    int,
    Field(
        description=(
            "录制持续时长，单位为秒。"
            "绝对不是 Unix 时间戳（如 1700000000）也不是毫秒时间戳（如 1700000000000）。"
            "0 表示读取最新历史流量包。"
        ),
        json_schema_extra={
            "minimum": 0,
            "maximum": 7200,
            "examples": [0, 5, 30, 120],
        },
    ),
]

HostContains = Annotated[
    Optional[str],
    Field(
        description="按 host 子串过滤（包含匹配）。例如：api.example.com",
        json_schema_extra={"examples": ["api.example.com", "gateway", "mmtls"]},
    ),
]

HttpMethodFilter = Annotated[
    Optional[str],
    Field(
        description=(
            "HTTP 方法过滤。仅允许标准 HTTP 方法。"
            "必须是方法名，不是正则表达式，不是路径。"
        ),
        json_schema_extra={"enum": list(HTTP_METHOD_CHOICES)},
    ),
]

KeywordRegex = Annotated[
    Optional[str],
    Field(
        description=(
            "用于搜索请求/响应内容的 Python 正则表达式。"
            "建议使用短表达式，避免灾难性回溯。"
        ),
        json_schema_extra={"maxLength": 500, "examples": ["token", "session|csrf", "password"]},
    ),
]

ThrottlingPreset = Annotated[
    str,
    Field(
        description=(
            "弱网预设名称。"
            "仅允许固定值：3G/4G/5G/fibre/100mbps/56k/256k/deactivate/off/on/start。"
        ),
        json_schema_extra={"enum": list(THROTTLING_PRESET_CHOICES)},
    ),
]


def _build_tool_guidance_error(
    *,
    parameter: str,
    received: Any,
    reason: str,
    valid_input: str,
    retry_example: str,
) -> list[dict]:
    """构造统一的可重试错误结构，避免只返回生硬异常。"""
    return [
        {
            "error": f"参数 `{parameter}` 无效：{reason}",
            "received": received,
            "valid_input": valid_input,
            "retry_example": retry_example,
        }
    ]


def _seconds_input_error(
    *,
    parameter: str,
    value: int,
    max_allowed: int,
    retry_example: str,
) -> Optional[list[dict]]:
    """校验录制时长参数，并返回可重试的引导信息。"""
    if value < 0:
        return _build_tool_guidance_error(
            parameter=parameter,
            received=value,
            reason="不能为负数。",
            valid_input=f"必须为 0 到 {max_allowed} 的整数秒。",
            retry_example=retry_example,
        )

    if value > max_allowed:
        timestamp_hint = ""
        if value >= 1_000_000_000_000:
            timestamp_hint = "你传入的值看起来是毫秒时间戳。"
        elif value >= 1_000_000_000:
            timestamp_hint = "你传入的值看起来是 Unix 秒级时间戳。"
        elif value > 86400:
            timestamp_hint = "该值远大于常见抓包时长。"

        reason = f"超过服务端允许上限 {max_allowed} 秒。{timestamp_hint}".strip()
        return _build_tool_guidance_error(
            parameter=parameter,
            received=value,
            reason=reason,
            valid_input=f"只能输入持续时长秒数，范围 0~{max_allowed}。",
            retry_example=retry_example,
        )

    return None


def _normalize_http_method(method: Optional[str]) -> tuple[Optional[str], Optional[list[dict]]]:
    """归一化 HTTP 方法并返回校验错误（如有）。"""
    if method is None:
        return (None, None)

    method_clean = method.strip().upper()
    if not method_clean:
        return (None, None)

    if method_clean not in HTTP_METHOD_CHOICES:
        return (
            None,
            _build_tool_guidance_error(
                parameter="http_method",
                received=method,
                reason="不是受支持的 HTTP 方法。",
                valid_input=f"仅允许: {', '.join(HTTP_METHOD_CHOICES)}",
                retry_example='filter_func(capture_seconds=0, http_method="POST")',
            ),
        )

    return (method_clean, None)


def _normalize_text_filter(value: Optional[str]) -> Optional[str]:
    """将空字符串归一化为 None，减少误调用噪音。"""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _guidance_error_message(error_payload: list[dict]) -> str:
    """Flatten a legacy guidance payload into a readable exception string."""
    if not error_payload:
        return "invalid tool input"
    first = error_payload[0]
    parts = [str(first.get("error", "invalid tool input"))]
    if first.get("valid_input"):
        parts.append(f"valid_input={first['valid_input']}")
    if first.get("retry_example"):
        parts.append(f"retry_example={first['retry_example']}")
    return "; ".join(parts)


# ==================== 配置备份与恢复 ====================

def backup_config(config: Config) -> bool:
    """
    备份 Charles 配置文件到项目备份目录。

    Args:
        config: 配置对象

    Returns:
        bool: 是否备份成功
    """
    if not config.config_path or not os.path.exists(config.config_path):
        logger.warning(f"找不到 Charles 配置文件: {config.config_path}")
        return False

    cfg_back_dir = os.path.join(config.backup_dir, "config")
    ensure_directory(cfg_back_dir)

    success = safe_copy_file(
        config.config_path,
        os.path.join(cfg_back_dir, "charles.config"),
    )

    # 备份 profiles 目录
    if config.profiles_dir and os.path.exists(config.profiles_dir):
        prf_back_dir = os.path.join(config.backup_dir, "profiles")
        safe_copy_tree(config.profiles_dir, prf_back_dir, remove_existing=True)

    if success:
        logger.info("Charles 配置备份完成")
    return success


async def restore_config(config: Config) -> bool:
    """
    恢复 Charles 配置并清理流量数据。

    执行步骤:
    1. 发送退出命令给 Charles
    2. 恢复配置文件
    3. 恢复 profiles 目录
    4. 清理流量包目录

    Args:
        config: 配置对象

    Returns:
        bool: 是否恢复成功
    """
    logger.info("正在执行环境重置...")

    # 发送退出命令
    try:
        async with CharlesClient(config) as client:
            await client.quit_charles()
            await asyncio.sleep(2)
    except CharlesClientError as e:
        logger.warning(f"发送退出命令失败 (可忽略): {e}")

    # 恢复 Config
    cfg_source = os.path.join(config.backup_dir, "config", "charles.config")
    if os.path.exists(cfg_source) and config.config_path:
        safe_copy_file(cfg_source, config.config_path)

    # 恢复 Profiles
    prf_source = os.path.join(config.backup_dir, "profiles")
    if os.path.exists(prf_source) and config.profiles_dir:
        safe_copy_tree(prf_source, config.profiles_dir, remove_existing=True)

    # 清理流量包目录
    safe_remove_tree(config.package_dir)
    ensure_directory(config.package_dir)

    logger.info("环境重置完成")
    return True


# ==================== MCP 服务器 ====================

def create_server(config: Optional[Config] = None) -> FastMCP:
    """
    创建并配置 MCP 服务器。

    Args:
        config: 配置对象，如果为 None 则使用全局配置

    Returns:
        FastMCP: 配置好的 MCP 服务器实例

    Example:
        >>> server = create_server()
        >>> server.run(transport="stdio")
    """
    config = config or get_config()

    # 验证配置
    warnings = config.validate()
    for w in warnings:
        logger.warning(w)

    # ==================== 生命周期管理 ====================

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        """MCP 服务器生命周期管理。"""
        logger.info("MCP 服务生命周期开始")

        if config.manage_charles_lifecycle:
            backup_config(config)

        try:
            yield {"config": config}
        finally:
            if config.manage_charles_lifecycle:
                await restore_config(config)
            logger.info("MCP 服务生命周期结束")

    mcp = FastMCP("CharlesMCP", json_response=True, lifespan=lifespan)
    live_service = LiveCaptureService(config, client_factory=CharlesClient)
    history_service = RecordingHistoryService(config, client_factory=CharlesClient)
    traffic_normalizer = TrafficNormalizer(config)
    traffic_analysis_service = TrafficAnalysisService()
    traffic_query_service = TrafficQueryService(
        live_service=live_service,
        history_service=history_service,
        normalizer=traffic_normalizer,
        analysis_service=traffic_analysis_service,
    )

    # ==================== 核心数据获取 ====================

    async def _get_proxy_data(record_seconds: int, ctx: Context) -> list[dict]:
        """
        获取流量数据的核心方法。

        Args:
            record_seconds: 录制时长(秒)，0 表示读取最新历史数据
            ctx: MCP 上下文

        Returns:
            list[dict]: 流量数据列表
        """
        ensure_directory(config.package_dir)

        if record_seconds > 0:
            try:
                await ctx.info("正在操作 Charles 录制流量...")
                async with CharlesClient(config) as client:
                    save_path = client.get_full_save_path()

                    async def on_progress(current: int, total: int) -> None:
                        remaining = total - current
                        await ctx.info(f"录制中... 剩余 {remaining}s")

                    return await client.record_session(
                        duration=record_seconds,
                        save_path=save_path,
                        progress_callback=on_progress,
                    )
            except CharlesClientError as e:
                err_msg = f"抓包过程出错: {e}"
                logger.error(err_msg)
                await ctx.error(err_msg)
                return [{"error": str(e)}]
            except Exception as e:
                err_msg = f"未预期的错误: {e}"
                logger.error(err_msg, exc_info=True)
                await ctx.error(err_msg)
                return [{"error": str(e)}]
        else:
            try:
                return await history_service.load_latest()
            except FileNotFoundError as e:
                return [{"error": str(e)}]
            except json.JSONDecodeError as e:
                return [{"error": f"解析历史数据失败: {e}"}]

    # ==================== MCP 工具定义 ====================

    def _build_traffic_query(
        *,
        preset: TrafficPreset = "api_focus",
        host_contains: Optional[str] = None,
        path_contains: Optional[str] = None,
        method_in: Optional[list[str]] = None,
        status_in: Optional[list[int]] = None,
        resource_class_in: Optional[list[str]] = None,
        min_priority_score: Optional[int] = None,
        request_body_contains: Optional[str] = None,
        response_body_contains: Optional[str] = None,
        request_header_name: Optional[str] = None,
        request_header_value_contains: Optional[str] = None,
        response_header_name: Optional[str] = None,
        response_header_value_contains: Optional[str] = None,
        request_content_type: Optional[str] = None,
        response_content_type: Optional[str] = None,
        request_json_query: Optional[str] = None,
        response_json_query: Optional[str] = None,
        include_sensitive: bool = False,
        include_body_preview: bool = True,
        max_items: int = 20,
        max_preview_chars: int = 256,
        max_headers_per_side: int = 8,
        scan_limit: int = 500,
    ) -> TrafficQuery:
        return TrafficQuery(
            preset=preset,
            host_contains=_normalize_text_filter(host_contains),
            path_contains=_normalize_text_filter(path_contains),
            method_in=[item.strip().upper() for item in (method_in or []) if item and item.strip()],
            status_in=[item for item in (status_in or []) if isinstance(item, int)],
            resource_class_in=[item for item in (resource_class_in or []) if item],
            min_priority_score=min_priority_score,
            request_body_contains=_normalize_text_filter(request_body_contains),
            response_body_contains=_normalize_text_filter(response_body_contains),
            request_header_name=_normalize_text_filter(request_header_name),
            request_header_value_contains=_normalize_text_filter(request_header_value_contains),
            response_header_name=_normalize_text_filter(response_header_name),
            response_header_value_contains=_normalize_text_filter(response_header_value_contains),
            request_content_type=_normalize_text_filter(request_content_type),
            response_content_type=_normalize_text_filter(response_content_type),
            request_json_query=_normalize_text_filter(request_json_query),
            response_json_query=_normalize_text_filter(response_json_query),
            include_sensitive=include_sensitive,
            include_body_preview=include_body_preview,
            max_items=max_items,
            max_preview_chars=max_preview_chars,
            max_headers_per_side=max_headers_per_side,
            scan_limit=scan_limit,
        )

    @mcp.tool()
    async def start_live_capture(
        reset_session: bool = True,
        include_existing: bool = False,
        adopt_existing: bool = False,
    ) -> LiveCaptureStartResult:
        """Start or adopt a live capture session for incremental polling."""
        try:
            return await live_service.start(
                reset_session=reset_session,
                include_existing=include_existing,
                adopt_existing=adopt_existing,
            )
        except Exception as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    async def read_live_capture(
        capture_id: str,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> LiveCaptureReadResult:
        """Read incremental traffic from the current Charles session without history fallback."""
        try:
            return await live_service.read(
                capture_id,
                cursor=cursor,
                limit=limit,
            )
        except Exception as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    async def peek_live_capture(
        capture_id: str,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> LiveCaptureReadResult:
        """Preview incremental traffic without advancing the live cursor."""
        try:
            return await live_service.read(
                capture_id,
                cursor=cursor,
                limit=limit,
                advance=False,
            )
        except Exception as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    async def stop_live_capture(
        capture_id: str,
        persist: bool = True,
    ) -> StopLiveCaptureResult:
        """Stop an active live capture and optionally persist the filtered snapshot."""
        try:
            return await live_service.stop(capture_id, persist=persist)
        except Exception as e:
            raise ValueError(str(e)) from e

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
        query = _build_traffic_query(
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
        return await traffic_query_service.analyze_live_capture(
            capture_id=capture_id,
            query=query,
            cursor=cursor,
        )

    @mcp.tool()
    async def analyze_recorded_traffic(
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
        include_sensitive: bool = False,
        include_body_preview: bool = True,
        max_items: int = 20,
        max_preview_chars: int = 256,
        max_headers_per_side: int = 8,
        scan_limit: int = 500,
    ) -> TrafficQueryResult:
        """Analyze a saved recording snapshot with compact, redacted summaries."""
        query = _build_traffic_query(
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
        return await traffic_query_service.analyze_recorded_traffic(
            recording_path=recording_path,
            query=query,
        )

    @mcp.tool()
    async def get_traffic_entry_detail(
        source: str,
        entry_id: str,
        capture_id: Optional[str] = None,
        recording_path: Optional[str] = None,
        include_sensitive: bool = False,
        include_full_body: bool = False,
        max_body_chars: int = 4096,
    ) -> TrafficDetailResult:
        """Load one traffic entry detail view for drill-down inspection."""
        return await traffic_query_service.get_detail(
            source=source,
            entry_id=entry_id,
            capture_id=capture_id,
            recording_path=recording_path,
            include_sensitive=include_sensitive,
            include_full_body=include_full_body,
            max_body_chars=max_body_chars,
        )

    @mcp.tool()
    async def get_capture_analysis_stats(
        source: str,
        capture_id: Optional[str] = None,
        recording_path: Optional[str] = None,
        preset: TrafficPreset = "api_focus",
        scan_limit: int = 500,
    ) -> CaptureAnalysisStatsResult:
        """Return coarse traffic class counts for a live capture or saved recording."""
        return await traffic_query_service.get_stats(
            source=source,
            capture_id=capture_id,
            recording_path=recording_path,
            preset=preset,
            scan_limit=scan_limit,
        )

    @mcp.tool()
    async def group_capture_analysis(
        source: str,
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
        include_sensitive: bool = False,
        max_groups: int = 10,
        max_preview_chars: int = 256,
        max_headers_per_side: int = 8,
        scan_limit: int = 500,
    ) -> CaptureAnalysisGroupsResult:
        """Group analyzed traffic so the agent can inspect hot spots with lower token cost."""
        query = _build_traffic_query(
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
            include_body_preview=False,
            max_items=max_groups,
            max_preview_chars=max_preview_chars,
            max_headers_per_side=max_headers_per_side,
            scan_limit=scan_limit,
        )
        return await traffic_query_service.group_capture(
            source=source,
            group_by=group_by,
            capture_id=capture_id,
            recording_path=recording_path,
            query=query,
            max_groups=max_groups,
        )

    @mcp.tool()
    async def query_recorded_traffic(
        host_contains: HostContains = None,
        http_method: HttpMethodFilter = None,
        keyword_regex: KeywordRegex = None,
        keep_request: bool = True,
        keep_response: bool = True,
    ) -> RecordedTrafficQueryResult:
        """Query the latest saved recording. This tool never reads the live Charles session."""
        host_contains_normalized = _normalize_text_filter(host_contains)
        method_normalized, method_error = _normalize_http_method(http_method)
        if method_error:
            raise ValueError(_guidance_error_message(method_error))

        if keyword_regex:
            valid, error_msg = history_service.validate_keyword_regex(keyword_regex)
            if not valid:
                raise ValueError(
                    _guidance_error_message(
                        _build_tool_guidance_error(
                            parameter="keyword_regex",
                            received=keyword_regex,
                            reason=f"invalid regex: {error_msg}",
                            valid_input="Provide a valid Python regular expression.",
                            retry_example='query_recorded_traffic(keyword_regex="token|session")',
                        )
                    )
                )

        return await history_service.query_latest_result(
            host_contains=host_contains_normalized,
            method_normalized=method_normalized,
            keyword_regex=keyword_regex,
            keep_request=keep_request,
            keep_response=keep_response,
        )

    @mcp.tool()
    async def proxy_by_time(record_seconds: RecordSeconds, ctx: Context) -> list[dict]:
        """抓取或读取 Charles 流量包。

        Deprecated for live analysis: this tool only records a fixed-duration snapshot
        or reads the latest saved `.chlsj` history file. It does not stream the current
        live Charles session.

        绝对规则（机器执行）:
        1. `record_seconds` 只表示“持续时长（秒）”。
        2. `record_seconds` 绝对不是 Unix 时间戳（例如 1700000000）。
        3. `record_seconds` 绝对不是毫秒时间戳（例如 1700000000000）。
        4. `record_seconds=0` 的唯一含义是“读取最新历史包”。

        Args:
            record_seconds: 录制持续时长（秒）。0 表示读取最新历史包。

        Returns:
            流量数据列表，每项包含 host, method, path, request, response 等字段。

        Examples:
            proxy_by_time(record_seconds=30) -> 录制 30 秒流量
            proxy_by_time(record_seconds=0)  -> 读取最新历史包
        """
        logger.info(f"Tool called: proxy_by_time(record_seconds={record_seconds})")

        seconds_error = _seconds_input_error(
            parameter="record_seconds",
            value=record_seconds,
            max_allowed=config.max_stoptime,
            retry_example="proxy_by_time(record_seconds=30)",
        )
        if seconds_error:
            return seconds_error

        return await _get_proxy_data(record_seconds, ctx)

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
        """高级过滤与搜索工具。

        Deprecated for live analysis: this tool filters a bounded capture or the latest
        saved history snapshot. It does not read incremental data from an active live capture.

        绝对规则（机器执行）:
        1. `capture_seconds` 是抓包持续时长（秒），不是时间戳。
        2. `http_method` 只能是标准 HTTP 方法名（如 GET/POST），不是正则。
        3. `keyword_regex` 是 Python 正则表达式，不是 SQL/通配符语法。

        Args:
            capture_seconds: 录制时长 (秒)。0 为使用最新历史数据。
            host_contains: 按域名过滤 (包含匹配)。
            http_method: 按 HTTP 方法过滤 (GET/POST/PUT/DELETE 等)。
            keyword_regex: 正则表达式搜索关键字。
            keep_request: 是否在结果中保留请求数据。
            keep_response: 是否在结果中保留响应数据。

        Returns:
            过滤后的流量数据列表。匹配的条目会附加 `_match_location` 字段。

        Examples:
            filter_func(capture_seconds=30, host_contains="api.example.com")
            filter_func(capture_seconds=0, keyword_regex="token")
        """
        logger.info(
            "Tool called: filter_func("
            f"capture_seconds={capture_seconds}, host_contains={host_contains}, http_method={http_method})"
        )

        seconds_error = _seconds_input_error(
            parameter="capture_seconds",
            value=capture_seconds,
            max_allowed=config.max_stoptime,
            retry_example='filter_func(capture_seconds=30, host_contains="api.example.com")',
        )
        if seconds_error:
            return seconds_error

        host_contains = _normalize_text_filter(host_contains)
        method_normalized, method_error = _normalize_http_method(http_method)
        if method_error:
            return method_error

        if keyword_regex:
            valid, error_msg = validate_regex(keyword_regex)
            if not valid:
                return _build_tool_guidance_error(
                    parameter="keyword_regex",
                    received=keyword_regex,
                    reason=f"无效的正则表达式：{error_msg}",
                    valid_input="请提供简洁且语法正确的 Python 正则表达式。",
                    retry_example='filter_func(capture_seconds=0, keyword_regex="token|session")',
                )

        raw_data = await _get_proxy_data(capture_seconds, ctx)
        if not isinstance(raw_data, list):
            return raw_data

        return _filter_entries(
            raw_data,
            host_contains=host_contains,
            method_normalized=method_normalized,
            keyword_regex=keyword_regex,
            keep_request=keep_request,
            keep_response=keep_response,
        )

    @mcp.tool()
    async def throttling(preset: ThrottlingPreset) -> str:
        """设置弱网预设。

        绝对规则（机器执行）:
        1. `preset` 只能使用固定预设名，不接受数字时长、不接受带单位字符串。
        2. `on/start` 会被映射为 `3G`。
        3. `off/deactivate` 会关闭节流。

        支持的预设:
        - '3G': 3G 网络
        - '4G': 4G 网络
        - '5G': 5G 网络
        - 'fibre' / '100mbps': 100+Mbps 光纤
        - '56k': 56kbps 拨号
        - 'deactivate' / 'off': 关闭节流
        - 'on' / 'start': 开启节流 (默认 3G)

        Args:
            preset: 网络预设名称或控制指令

        Returns:
            操作结果消息

        Examples:
            throttling("3G") -> 设置 3G 网络
            throttling("off") -> 关闭弱网模拟
        """
        logger.info(f"Tool called: throttling(preset={preset})")

        preset_clean = preset.strip()
        if not preset_clean:
            return (
                "Error: 参数 `preset` 不能为空。"
                "请使用固定预设值，例如: 3G / 4G / 5G / off / deactivate"
            )

        # 处理别名
        preset_lower = preset_clean.lower()
        if preset_lower not in {v.lower() for v in THROTTLING_PRESET_CHOICES}:
            return (
                "Error: 参数 `preset` 无效。"
                f"仅允许: {', '.join(THROTTLING_PRESET_CHOICES)}。"
                "请重试，例如 throttling(\"3G\") 或 throttling(\"off\")。"
            )

        normalized_preset = "3G" if preset_lower in ("start", "on") else preset_clean

        try:
            async with CharlesClient(config) as client:
                success, message = await client.set_throttling(normalized_preset)
                return f"{'Success' if success else 'Error'}: {message}"
        except CharlesClientError as e:
            logger.error(f"Throttling error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def reset_environment(ctx: Context) -> str:
        """手动重置环境。

        执行以下操作:
        1. 退出 Charles
        2. 恢复 Charles 配置文件
        3. 清理本地流量包数据

        Returns:
            重置结果消息
        """
        await ctx.info("正在执行手动重置...")
        try:
            await restore_config(config)
            return "环境重置完成"
        except Exception as e:
            logger.error(f"重置环境出错: {e}")
            return f"重置出错: {e}"

    @mcp.tool()
    async def list_sessions() -> list[dict]:
        """??????????????????????
        Returns:
            ?????????????????filename, size, path ?????

        Examples:
            list_sessions() -> ??????????????
        """
        logger.info("Tool called: list_sessions()")

        recordings = history_service.list_recordings_result()
        if not recordings.items:
            return [{"message": "?????????"}]
        return [item.model_dump() for item in recordings.items]

    @mcp.tool()
    async def list_recordings() -> RecordingListResult:
        """List saved recording files using an explicit history-oriented tool name."""
        return history_service.list_recordings_result()

    @mcp.tool()
    async def get_recording_snapshot(path: Optional[str] = None) -> RecordingSnapshotResult:
        """Load a saved recording snapshot. This tool never reads the live Charles session."""
        try:
            return await history_service.get_snapshot_result(path)
        except Exception as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    async def charles_status() -> CharlesStatusResult:
        """检查 Charles Proxy 连接状态。

        Returns:
            包含连接状态、配置信息的字典。

        Examples:
            charles_status() -> 查看 Charles 是否正常运行
        """
        logger.info("Tool called: charles_status()")

        active_capture = live_service.get_active_capture()
        result = CharlesStatusResult(
            config=CharlesStatusConfig(
                proxy_url=config.proxy_url,
                base_url=config.charles_base_url,
                config_path=config.config_path or "未检测到",
                manage_charles_lifecycle=config.manage_charles_lifecycle,
            ),
            live_capture=LiveCaptureRuntimeStatus(
                active_capture=ActiveCaptureStatus(**active_capture) if active_capture else None
            ),
            connected=False,
        )

        try:
            async with CharlesClient(config) as client:
                info = await client.get_info()
                result.connected = info is not None
                if info:
                    result.charles_info = info
        except CharlesClientError as e:
            result.connected = False
            result.error = str(e)

        return result

    return mcp
