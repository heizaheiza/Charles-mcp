"""Package entrypoint for the Charles MCP server."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from charles_mcp.server import create_server
from charles_mcp.utils import setup_logging, setup_windows_stdio


def main() -> None:
    """Start the Charles MCP server over stdio."""
    runtime_dir = Path.cwd()
    setup_logging(log_file=str(runtime_dir / "debug.log"))
    logger = logging.getLogger(__name__)
    logger.info(">>> Charles MCP Server 正在启动...")

    setup_windows_stdio()

    try:
        server = create_server()
        logger.info("调用 mcp.run()...")
        server.run(transport="stdio")
    except Exception as exc:
        logger.critical("Server Process Crashed: %s", exc, exc_info=True)
        sys.exit(1)
