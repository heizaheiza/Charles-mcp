import pytest

from charles_mcp.config import reset_config
from charles_mcp.server import create_server
from charles_mcp.tools.public_surface import LEGACY_COMPAT_TOOL_NAMES


@pytest.mark.asyncio
async def test_legacy_tools_are_exposed_when_explicit_compat_flag_is_true() -> None:
    server = create_server(expose_legacy_tools=True)
    tools = await server.list_tools()
    names = {tool.name for tool in tools}
    descriptions = {tool.name: (tool.description or "") for tool in tools}

    for tool_name in LEGACY_COMPAT_TOOL_NAMES:
        assert tool_name in names
        assert "deprecated compatibility alias" in descriptions[tool_name].lower()


@pytest.mark.asyncio
async def test_legacy_tools_are_exposed_when_env_toggle_is_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHARLES_EXPOSE_LEGACY_TOOLS", "true")
    reset_config()
    try:
        server = create_server()
        names = {tool.name for tool in await server.list_tools()}
        for tool_name in LEGACY_COMPAT_TOOL_NAMES:
            assert tool_name in names
    finally:
        reset_config()


@pytest.mark.asyncio
async def test_explicit_flag_takes_precedence_over_env_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHARLES_EXPOSE_LEGACY_TOOLS", "true")
    reset_config()
    try:
        server = create_server(expose_legacy_tools=False)
        names = {tool.name for tool in await server.list_tools()}
        for tool_name in LEGACY_COMPAT_TOOL_NAMES:
            assert tool_name not in names
    finally:
        reset_config()
