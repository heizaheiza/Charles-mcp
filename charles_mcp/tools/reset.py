from __future__ import annotations

import logging

from mcp.server.fastmcp import Context, FastMCP

from charles_mcp.client import CharlesClientError
from charles_mcp.schemas.status import (
    ActiveCaptureStatus,
    CharlesStatusConfig,
    CharlesStatusResult,
    LiveCaptureRuntimeStatus,
)
from charles_mcp.tools.tool_contract import (
    THROTTLING_PRESET_CHOICES,
    ThrottlingPreset,
    ToolDependencies,
    safe_ctx_log,
)

logger = logging.getLogger(__name__)


def register_reset_tools(
    mcp: FastMCP,
    *,
    deps: ToolDependencies,
    restore_config_fn,
) -> None:
    @mcp.tool()
    async def throttling(preset: ThrottlingPreset) -> str:
        """设置弱网预设。"""
        logger.info("Tool called: throttling(preset=%s)", preset)

        preset_clean = preset.strip()
        if not preset_clean:
            return (
                "Error: 参数 `preset` 不能为空。"
                "请使用固定预设值，例如: 3G / 4G / 5G / off / deactivate"
            )

        preset_lower = preset_clean.lower()
        if preset_lower not in {value.lower() for value in THROTTLING_PRESET_CHOICES}:
            return (
                "Error: 参数 `preset` 无效。"
                f"仅允许 {', '.join(THROTTLING_PRESET_CHOICES)}。"
                "请重试，例如 throttling(\"3G\") 或 throttling(\"off\")。"
            )

        normalized_preset = "3G" if preset_lower in ("start", "on") else preset_clean

        try:
            async with deps.client_factory(deps.config) as client:
                success, message = await client.set_throttling(normalized_preset)
                return f"{'Success' if success else 'Error'}: {message}"
        except CharlesClientError as exc:
            logger.error("Throttling error: %s", exc)
            return f"Error: {exc}"

    @mcp.tool()
    async def reset_environment(ctx: Context) -> str:
        """手动重置环境。"""
        await safe_ctx_log(ctx, "info", "正在执行手动重置...")
        try:
            await restore_config_fn(deps.config)
            return "环境重置完成"
        except Exception as exc:
            logger.error("重置环境出错: %s", exc)
            return f"重置出错: {exc}"

    @mcp.tool()
    async def list_sessions() -> list[dict]:
        """List historical session files via the legacy tool name."""
        logger.info("Tool called: list_sessions()")

        recordings = deps.history_service.list_recordings_result()
        if not recordings.items:
            return [{"message": "暂无录制文件"}]
        return [item.model_dump() for item in recordings.items]

    @mcp.tool()
    async def charles_status() -> CharlesStatusResult:
        """检查 Charles Proxy 连接状态。"""
        logger.info("Tool called: charles_status()")

        active_capture = deps.live_service.get_active_capture()
        result = CharlesStatusResult(
            config=CharlesStatusConfig(
                proxy_url=deps.config.proxy_url,
                base_url=deps.config.charles_base_url,
                config_path=deps.config.config_path or "未检测到",
                manage_charles_lifecycle=deps.config.manage_charles_lifecycle,
            ),
            live_capture=LiveCaptureRuntimeStatus(
                active_capture=ActiveCaptureStatus(**active_capture) if active_capture else None
            ),
            connected=False,
        )

        try:
            async with deps.client_factory(deps.config) as client:
                info = await client.get_info()
                result.connected = info is not None
                if info:
                    result.charles_info = info
        except CharlesClientError as exc:
            result.connected = False
            result.error = str(exc)

        return result
