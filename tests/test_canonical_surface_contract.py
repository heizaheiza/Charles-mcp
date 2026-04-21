import asyncio
import json
import re
from pathlib import Path

from charles_mcp.server import create_server
from charles_mcp.tools.public_surface import (
    CANONICAL_PUBLIC_TOOL_NAMES,
    LEGACY_COMPAT_TOOL_NAMES,
)


def _load_parseable_surface_payload() -> dict:
    text = Path("docs/contracts/tools.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- CANONICAL_PUBLIC_SURFACE:START -->\s*```json\s*(\{.*?\})\s*```\s*<!-- CANONICAL_PUBLIC_SURFACE:END -->",
        text,
        flags=re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_parseable_canonical_surface_matches_code_constants() -> None:
    payload = _load_parseable_surface_payload()

    assert payload["canonical_public_tool_names"] == list(CANONICAL_PUBLIC_TOOL_NAMES)
    assert payload["legacy_compat_tool_names"] == list(LEGACY_COMPAT_TOOL_NAMES)


def test_default_server_surface_matches_canonical_contract() -> None:
    async def _tool_names() -> set[str]:
        server = create_server()
        tools = await server.list_tools()
        return {tool.name for tool in tools}

    names = asyncio.run(_tool_names())
    assert names == set(CANONICAL_PUBLIC_TOOL_NAMES)
    assert names.isdisjoint(LEGACY_COMPAT_TOOL_NAMES)
