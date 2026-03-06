import asyncio
import json
from pathlib import Path

import pytest

from charles_mcp.config import Config
from charles_mcp.server import create_server


def _tool_result(call_result):
    payload = call_result[1]
    return payload["result"] if isinstance(payload, dict) and "result" in payload else payload


def _tool_output_schema(tool_name: str) -> dict | None:
    async def _get_schema():
        server = create_server()
        tools = await server.list_tools()
        for tool in tools:
            if tool.name == tool_name:
                return tool.outputSchema
        return None

    return asyncio.run(_get_schema())


def test_history_tools_have_structured_output_schema() -> None:
    query_schema = _tool_output_schema("query_recorded_traffic")
    list_schema = _tool_output_schema("list_recordings")
    snapshot_schema = _tool_output_schema("get_recording_snapshot")

    assert query_schema is not None
    assert "properties" in query_schema
    assert "items" in query_schema["properties"]
    assert "total_items" in query_schema["properties"]
    assert "source" in query_schema["properties"]

    assert list_schema is not None
    assert "properties" in list_schema
    assert "items" in list_schema["properties"]
    assert "total_items" in list_schema["properties"]

    assert snapshot_schema is not None
    assert "properties" in snapshot_schema
    assert "items" in snapshot_schema["properties"]
    assert "total_items" in snapshot_schema["properties"]
    assert "source" in snapshot_schema["properties"]


@pytest.mark.asyncio
async def test_list_recordings_returns_structured_payload(tmp_path: Path) -> None:
    config = Config(base_dir=str(tmp_path))
    snapshot = [{"host": "api.example.com", "path": "/history"}]
    (tmp_path / "package").mkdir(parents=True, exist_ok=True)
    recording_path = tmp_path / "package" / "20260306010101.chlsj"
    recording_path.write_text(json.dumps(snapshot), encoding="utf-8")

    server = create_server(config)
    call_result = await server.call_tool("list_recordings", {})
    result = _tool_result(call_result)

    assert result["total_items"] == 1
    assert result["warnings"] == []
    assert result["items"][0]["filename"] == "20260306010101.chlsj"
    assert result["items"][0]["path"] == str(recording_path)


@pytest.mark.asyncio
async def test_get_recording_snapshot_returns_structured_payload(tmp_path: Path) -> None:
    config = Config(base_dir=str(tmp_path))
    snapshot = [{"host": "api.example.com", "path": "/snapshot"}]
    recording_path = tmp_path / "package" / "manual.chlsj"
    recording_path.parent.mkdir(parents=True, exist_ok=True)
    recording_path.write_text(json.dumps(snapshot), encoding="utf-8")

    server = create_server(config)
    call_result = await server.call_tool(
        "get_recording_snapshot",
        {"path": str(recording_path)},
    )
    result = _tool_result(call_result)

    assert result["source"] == "history"
    assert result["path"] == str(recording_path)
    assert result["total_items"] == 1
    assert result["items"][0]["path"] == "/snapshot"
