import asyncio

from charles_mcp.config import Config
from charles_mcp.server import create_server
from charles_mcp.tools import ToolDependencies


def test_create_server_registers_public_lifespan() -> None:
    server = create_server(Config())

    assert server.settings.lifespan is not None


async def _lifespan_context(server):
    async with server.settings.lifespan(server) as context:
        return context


def test_public_lifespan_yields_typed_tool_dependencies() -> None:
    server = create_server(Config())

    context = asyncio.run(_lifespan_context(server))

    assert isinstance(context, ToolDependencies)
    assert getattr(server, "_charles_tool_dependencies") is context
