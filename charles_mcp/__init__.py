"""
Charles MCP Server - 将 Charles Proxy 集成到 MCP 协议的工具包。

This package provides:
- CharlesClient: 异步 Charles API 客户端
- MCP Server: 提供抓包、过滤、弱网模拟等工具

Example:
    >>> from charles_mcp.server import create_server
    >>> server = create_server()
    >>> server.run(transport="stdio")
"""

__version__ = "2.0.0"
__author__ = "7owe2"

from charles_mcp.config import Config
from charles_mcp.client import CharlesClient

__all__ = ["Config", "CharlesClient", "__version__"]
