from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Optional, cast

from mcp.server.fastmcp import Context
from pydantic import Field

from charles_mcp.client import CharlesClientError
from charles_mcp.config import Config
from charles_mcp.schemas.traffic_query import TrafficPreset, TrafficQuery
from charles_mcp.services.history_capture import RecordingHistoryService
from charles_mcp.services.live_capture import LiveCaptureService
from charles_mcp.services.traffic_query_service import TrafficQueryService
from charles_mcp.utils import (
    ensure_directory,
    safe_copy_file,
    safe_copy_tree,
    safe_remove_tree,
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


@dataclass(frozen=True)
class ToolDependencies:
    config: Config
    client_factory: Any
    live_service: LiveCaptureService
    history_service: RecordingHistoryService
    traffic_query_service: TrafficQueryService
    restore_config_fn: Callable[[Config], Awaitable[bool]]


ToolContext = Context[Any, ToolDependencies, Any]
_TOOL_DEPENDENCIES_ATTR = "_charles_tool_dependencies"


def attach_tool_dependencies(server: Any, deps: ToolDependencies) -> None:
    setattr(server, _TOOL_DEPENDENCIES_ATTR, deps)


def get_tool_dependencies(ctx: ToolContext) -> ToolDependencies:
    try:
        return ctx.request_context.lifespan_context
    except ValueError:
        fastmcp = ctx.fastmcp
        deps = getattr(fastmcp, _TOOL_DEPENDENCIES_ATTR, None)
        if deps is None:
            raise ValueError("Tool dependencies are unavailable outside of a request") from None
        return cast(ToolDependencies, deps)


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


def build_tool_guidance_error(
    *,
    parameter: str,
    received: Any,
    reason: str,
    valid_input: str,
    retry_example: str,
) -> list[dict]:
    return [
        {
            "error": f"参数 `{parameter}` 无效，{reason}",
            "received": received,
            "valid_input": valid_input,
            "retry_example": retry_example,
        }
    ]


def seconds_input_error(
    *,
    parameter: str,
    value: int,
    max_allowed: int,
    retry_example: str,
) -> Optional[list[dict]]:
    if value < 0:
        return build_tool_guidance_error(
            parameter=parameter,
            received=value,
            reason="不能为负数。",
            valid_input=f"必须为 0 到 {max_allowed} 的整数秒。",
            retry_example=retry_example,
        )

    if value > max_allowed:
        timestamp_hint = ""
        if value >= 1_000_000_000_000:
            timestamp_hint = "你传入的值看起来像是毫秒时间戳。"
        elif value >= 1_000_000_000:
            timestamp_hint = "你传入的值看起来像 Unix 秒级时间戳。"
        elif value > 86400:
            timestamp_hint = "该值远大于常见抓包时长。"

        reason = f"超过服务端允许上限 {max_allowed} 秒。{timestamp_hint}".strip()
        return build_tool_guidance_error(
            parameter=parameter,
            received=value,
            reason=reason,
            valid_input=f"只能输入持续时长秒数，范围 0~{max_allowed}。",
            retry_example=retry_example,
        )

    return None


def normalize_http_method(method: Optional[str]) -> tuple[Optional[str], Optional[list[dict]]]:
    if method is None:
        return (None, None)

    method_clean = method.strip().upper()
    if not method_clean:
        return (None, None)

    if method_clean not in HTTP_METHOD_CHOICES:
        return (
            None,
            build_tool_guidance_error(
                parameter="http_method",
                received=method,
                reason="不是受支持的 HTTP 方法。",
                valid_input=f"仅允许 {', '.join(HTTP_METHOD_CHOICES)}",
                retry_example='filter_func(capture_seconds=0, http_method="POST")',
            ),
        )

    return (method_clean, None)


def normalize_text_filter(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def guidance_error_message(error_payload: list[dict]) -> str:
    if not error_payload:
        return "invalid tool input"
    first = error_payload[0]
    parts = [str(first.get("error", "invalid tool input"))]
    if first.get("valid_input"):
        parts.append(f"valid_input={first['valid_input']}")
    if first.get("retry_example"):
        parts.append(f"retry_example={first['retry_example']}")
    return "; ".join(parts)


async def safe_ctx_log(ctx: Context, level: str, message: str) -> None:
    try:
        log_fn = getattr(ctx, level)
        await log_fn(message)
    except ValueError:
        logger.debug("Skipping ctx.%s log outside request context: %s", level, message)


def backup_config(config: Config) -> bool:
    if not config.config_path or not os.path.exists(config.config_path):
        logger.warning("找不到 Charles 配置文件: %s", config.config_path)
        return False

    cfg_back_dir = os.path.join(config.backup_dir, "config")
    ensure_directory(cfg_back_dir)

    success = safe_copy_file(
        config.config_path,
        os.path.join(cfg_back_dir, "charles.config"),
    )

    if config.profiles_dir and os.path.exists(config.profiles_dir):
        prf_back_dir = os.path.join(config.backup_dir, "profiles")
        safe_copy_tree(config.profiles_dir, prf_back_dir, remove_existing=True)

    if success:
        logger.info("Charles 配置备份完成")
    return success


async def restore_config(config: Config, *, client_factory: Any) -> bool:
    logger.info("正在执行环境重置...")

    try:
        async with client_factory(config) as client:
            await client.quit_charles()
            await asyncio.sleep(2)
    except CharlesClientError as exc:
        logger.warning("发送退出命令失败(可忽略): %s", exc)

    cfg_source = os.path.join(config.backup_dir, "config", "charles.config")
    if os.path.exists(cfg_source) and config.config_path:
        safe_copy_file(cfg_source, config.config_path)

    prf_source = os.path.join(config.backup_dir, "profiles")
    if os.path.exists(prf_source) and config.profiles_dir:
        safe_copy_tree(prf_source, config.profiles_dir, remove_existing=True)

    safe_remove_tree(config.package_dir)
    ensure_directory(config.package_dir)

    logger.info("环境重置完成")
    return True


async def get_proxy_data(
    record_seconds: int,
    ctx: Context,
    *,
    deps: ToolDependencies,
) -> list[dict]:
    ensure_directory(deps.config.package_dir)

    if record_seconds > 0:
        try:
            await safe_ctx_log(ctx, "info", "正在操作 Charles 录制流量...")
            async with deps.client_factory(deps.config) as client:
                save_path = client.get_full_save_path()

                async def on_progress(current: int, total: int) -> None:
                    remaining = total - current
                    await safe_ctx_log(ctx, "info", f"录制中... 剩余 {remaining}s")

                return await client.record_session(
                    duration=record_seconds,
                    save_path=save_path,
                    progress_callback=on_progress,
                )
        except CharlesClientError as exc:
            err_msg = f"抓包过程出错: {exc}"
            logger.error(err_msg)
            await safe_ctx_log(ctx, "error", err_msg)
            return [{"error": str(exc)}]
        except Exception as exc:  # pragma: no cover - defensive logging path
            err_msg = f"未预期的错误: {exc}"
            logger.error(err_msg, exc_info=True)
            await safe_ctx_log(ctx, "error", err_msg)
            return [{"error": str(exc)}]

    try:
        return await deps.history_service.load_latest()
    except FileNotFoundError as exc:
        return [{"error": str(exc)}]
    except json.JSONDecodeError as exc:
        return [{"error": f"解析历史数据失败: {exc}"}]


def build_traffic_query(
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
    include_body_preview: bool = True,
    max_items: int = 20,
    max_preview_chars: int = 256,
    max_headers_per_side: int = 8,
    scan_limit: int = 500,
) -> TrafficQuery:
    return TrafficQuery(
        preset=preset,
        host_contains=normalize_text_filter(host_contains),
        path_contains=normalize_text_filter(path_contains),
        method_in=[item.strip().upper() for item in (method_in or []) if item and item.strip()],
        status_in=[item for item in (status_in or []) if isinstance(item, int)],
        resource_class_in=[item for item in (resource_class_in or []) if item],
        min_priority_score=min_priority_score,
        request_body_contains=normalize_text_filter(request_body_contains),
        response_body_contains=normalize_text_filter(response_body_contains),
        request_header_name=normalize_text_filter(request_header_name),
        request_header_value_contains=normalize_text_filter(request_header_value_contains),
        response_header_name=normalize_text_filter(response_header_name),
        response_header_value_contains=normalize_text_filter(response_header_value_contains),
        request_content_type=normalize_text_filter(request_content_type),
        response_content_type=normalize_text_filter(response_content_type),
        request_json_query=normalize_text_filter(request_json_query),
        response_json_query=normalize_text_filter(response_json_query),
        include_body_preview=include_body_preview,
        max_items=max_items,
        max_preview_chars=max_preview_chars,
        max_headers_per_side=max_headers_per_side,
        scan_limit=scan_limit,
    )
