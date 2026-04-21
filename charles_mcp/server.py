"""Charles MCP server entrypoint and tool assembly."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from mcp.server.fastmcp import FastMCP

from charles_mcp.client import CharlesClient
from charles_mcp.config import Config, get_config
from charles_mcp.reverse.server import build_reverse_runtime, register_reverse_tools
from charles_mcp.services import (
    LiveCaptureService,
    RecordingHistoryService,
    TrafficAnalysisService,
    TrafficNormalizer,
    TrafficQueryService,
)
from charles_mcp.tools import (
    ToolDependencies,
    attach_tool_dependencies,
    backup_config as _backup_config,
    register_history_tools,
    register_legacy_tools,
    register_live_tools,
    register_reset_tools,
    restore_config as _restore_config,
)

logger = logging.getLogger(__name__)


def backup_config(config: Config) -> bool:
    """Compatibility wrapper kept for lifecycle tests and monkeypatching."""
    return _backup_config(config)


async def restore_config(config: Config) -> bool:
    """Compatibility wrapper kept for lifecycle tests and monkeypatching."""
    return await _restore_config(config, client_factory=CharlesClient)


def _resolve_expose_legacy_tools(
    config: Config,
    expose_legacy_tools: bool | None,
) -> bool:
    """Resolve legacy-tool exposure with explicit parameter precedence."""
    if expose_legacy_tools is not None:
        return expose_legacy_tools
    return config.expose_legacy_tools


def create_server(
    config: Optional[Config] = None,
    expose_legacy_tools: bool | None = None,
) -> FastMCP[ToolDependencies]:
    """
    Create and configure the Charles MCP server.

    Args:
        config: Optional configuration. Defaults to the global config.
        expose_legacy_tools: Explicit compatibility-layer toggle. When None,
            falls back to Config.expose_legacy_tools / CHARLES_EXPOSE_LEGACY_TOOLS.

    Returns:
        Configured FastMCP server instance.
    """
    config = config or get_config()
    compat_legacy = _resolve_expose_legacy_tools(config, expose_legacy_tools)

    warnings = config.validate()
    for warning in warnings:
        logger.warning(warning)

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
    reverse_runtime = build_reverse_runtime(config)
    deps = ToolDependencies(
        config=config,
        client_factory=CharlesClient,
        live_service=live_service,
        history_service=history_service,
        traffic_query_service=traffic_query_service,
        restore_config_fn=restore_config,
    )

    @asynccontextmanager
    async def lifespan(server: FastMCP[ToolDependencies]) -> AsyncIterator[ToolDependencies]:
        logger.info("MCP service lifespan started")

        if config.manage_charles_lifecycle:
            backup_config(config)

        try:
            yield deps
        finally:
            if config.manage_charles_lifecycle:
                await restore_config(config)
            reverse_runtime.store.close()
            logger.info("MCP service lifespan finished")

    mcp = FastMCP("CharlesMCP", json_response=True, lifespan=lifespan)
    attach_tool_dependencies(mcp, deps)

    register_live_tools(mcp)
    register_history_tools(mcp)
    register_reset_tools(mcp)
    register_reverse_tools(mcp, reverse_runtime)
    if compat_legacy:
        register_legacy_tools(mcp)

    return mcp
