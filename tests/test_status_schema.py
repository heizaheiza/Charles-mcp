import asyncio

from charles_mcp.server import create_server


def test_charles_status_tool_has_structured_output_schema() -> None:
    async def _get_schema():
        server = create_server()
        tools = await server.list_tools()
        for tool in tools:
            if tool.name == "charles_status":
                return tool.outputSchema
        return None

    schema = asyncio.run(_get_schema())

    assert schema is not None
    assert "properties" in schema
    assert "connected" in schema["properties"]
    assert "live_capture" in schema["properties"]
