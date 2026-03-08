from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

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
    ToolContext,
    get_tool_dependencies,
    safe_ctx_log,
)

logger = logging.getLogger(__name__)


def register_reset_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def throttling(ctx: ToolContext, preset: ThrottlingPreset) -> str:
        """Set a network throttling preset in Charles."""
        logger.info("Tool called: throttling(preset=%s)", preset)
        deps = get_tool_dependencies(ctx)

        preset_clean = preset.strip()
        if not preset_clean:
            return (
                "Error: parameter `preset` cannot be empty. "
                "Use one of the supported presets, for example: 3G / 4G / 5G / off / deactivate."
            )

        preset_lower = preset_clean.lower()
        supported = {value.lower() for value in THROTTLING_PRESET_CHOICES}
        if preset_lower not in supported:
            return (
                "Error: parameter `preset` is invalid. "
                f"Supported values: {', '.join(THROTTLING_PRESET_CHOICES)}. "
                'Retry with something like throttling("3G") or throttling("off").'
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
    async def reset_environment(ctx: ToolContext) -> str:
        """Reset the Charles environment and restore the saved configuration."""
        deps = get_tool_dependencies(ctx)
        await safe_ctx_log(ctx, "info", "Running manual environment reset...")
        try:
            await deps.restore_config_fn(deps.config)
            return "Environment reset completed"
        except Exception as exc:
            logger.error("Reset environment failed: %s", exc)
            return f"Reset failed: {exc}"

    @mcp.tool()
    async def list_sessions(ctx: ToolContext) -> list[dict]:
        """List historical session files via the legacy tool name."""
        logger.info("Tool called: list_sessions()")
        deps = get_tool_dependencies(ctx)

        recordings = deps.history_service.list_recordings_result()
        if not recordings.items:
            return [{"message": "No recordings available"}]
        return [item.model_dump() for item in recordings.items]

    @mcp.tool()
    async def charles_status(ctx: ToolContext) -> CharlesStatusResult:
        """Check Charles connectivity and active live-capture state."""
        logger.info("Tool called: charles_status()")
        deps = get_tool_dependencies(ctx)

        active_capture = deps.live_service.get_active_capture()
        result = CharlesStatusResult(
            config=CharlesStatusConfig(
                proxy_url=deps.config.proxy_url,
                base_url=deps.config.charles_base_url,
                config_path=deps.config.config_path or "not_detected",
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
