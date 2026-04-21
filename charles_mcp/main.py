"""Package entrypoint for the Charles MCP server."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

from charles_mcp.server import create_server
from charles_mcp.utils import setup_logging, setup_windows_stdio


def _resolve_log_dir() -> Path:
    """Return the log directory, respecting CHARLES_LOG_DIR env var."""
    env_dir = os.environ.get("CHARLES_LOG_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    return Path(tempfile.gettempdir()) / "charles-mcp"


def main() -> None:
    """Start the Charles MCP server over stdio."""
    log_dir = _resolve_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(log_file=str(log_dir / "debug.log"))
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
