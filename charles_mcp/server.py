"""Charles MCP server entrypoint and tool assembly."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from charles_mcp.client import CharlesClient
from charles_mcp.config import Config, get_config
from charles_mcp.services import (
    LiveCaptureService,
    RecordingHistoryService,
    TrafficAnalysisService,
    TrafficNormalizer,
    TrafficQueryService,
)
from charles_mcp.tools import (
    ToolDependencies,
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


def create_server(config: Optional[Config] = None) -> FastMCP:
    """
    Create and configure the Charles MCP server.

    Args:
        config: Optional configuration. Defaults to the global config.

    Returns:
        Configured FastMCP server instance.
    """
    config = config or get_config()

    warnings = config.validate()
    for warning in warnings:
        logger.warning(warning)

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        logger.info("MCP service lifespan started")

        if config.manage_charles_lifecycle:
            backup_config(config)

        try:
            yield {"config": config}
        finally:
            if config.manage_charles_lifecycle:
                await restore_config(config)
            logger.info("MCP service lifespan finished")

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
    deps = ToolDependencies(
        config=config,
        client_factory=CharlesClient,
        live_service=live_service,
        history_service=history_service,
        traffic_query_service=traffic_query_service,
    )

    register_live_tools(mcp, deps=deps)
    register_history_tools(mcp, deps=deps)
    register_legacy_tools(mcp, deps=deps)
    register_reset_tools(mcp, deps=deps, restore_config_fn=restore_config)

    return mcp
