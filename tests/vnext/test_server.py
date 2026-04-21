import pytest

import charles_mcp.reverse.server as server_module
from charles_mcp.reverse.models import CaptureSourceFormat
from charles_mcp.reverse.server import create_server


def _tool_result(call_result):
    payload = call_result[1]
    return payload["result"] if isinstance(payload, dict) and "result" in payload else payload


@pytest.mark.asyncio
async def test_vnext_tool_surface_is_registered() -> None:
    server = create_server()

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert len(tools) == len(names)
    assert names == {
        "reverse_analyze_live_api_flow",
        "reverse_analyze_live_login_flow",
        "reverse_analyze_live_signature_flow",
        "reverse_charles_recording_status",
        "reverse_decode_entry_body",
        "reverse_discover_signature_candidates",
        "reverse_get_entry_detail",
        "reverse_import_session",
        "reverse_list_captures",
        "reverse_list_findings",
        "reverse_peek_live_entries",
        "reverse_query_entries",
        "reverse_read_live_entries",
        "reverse_replay_entry",
        "reverse_start_live_analysis",
        "reverse_stop_live_analysis",
    }


@pytest.mark.asyncio
async def test_vnext_live_tool_schema_limits_snapshot_format_values() -> None:
    server = create_server()
    tools = {tool.name: tool for tool in await server.list_tools()}

    live_tool_names = {
        "reverse_start_live_analysis",
        "reverse_peek_live_entries",
        "reverse_read_live_entries",
        "reverse_analyze_live_login_flow",
        "reverse_analyze_live_api_flow",
        "reverse_analyze_live_signature_flow",
    }

    for tool_name in live_tool_names:
        snapshot_format = tools[tool_name].inputSchema["properties"]["snapshot_format"]
        assert snapshot_format["enum"] == ["xml", "native"]
        assert snapshot_format["default"] == "xml"


@pytest.mark.asyncio
async def test_vnext_start_live_analysis_coerces_summary_snapshot_format(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_start(self, **kwargs):
        captured.update(kwargs)
        snapshot_format = kwargs["snapshot_format"]
        return {"live_session_id": "live-test", "snapshot_format": snapshot_format.value}

    monkeypatch.setattr(server_module.LiveAnalysisService, "start", fake_start)

    server = create_server()
    result = _tool_result(await server.call_tool("reverse_start_live_analysis", {"snapshot_format": "summary"}))

    assert captured["snapshot_format"] is CaptureSourceFormat.XML
    assert result["snapshot_format"] == "xml"
    assert result["coerced_from"] == {"snapshot_format": "summary"}
    assert result["input_warnings"] == [
        "`snapshot_format=summary` is deprecated for live-session tools; using `xml`."
    ]

