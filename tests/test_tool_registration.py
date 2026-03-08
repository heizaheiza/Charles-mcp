import pytest

from charles_mcp.server import create_server


@pytest.mark.asyncio
async def test_live_and_history_tool_names_are_registered() -> None:
    server = create_server()

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert "start_live_capture" in names
    assert "read_live_capture" in names
    assert "peek_live_capture" in names
    assert "stop_live_capture" in names
    assert "query_recorded_traffic" in names
    assert "list_recordings" in names
    assert "get_recording_snapshot" in names
    assert "query_live_capture_entries" in names
    assert "analyze_recorded_traffic" in names
    assert "get_traffic_entry_detail" in names
    assert "get_capture_analysis_stats" in names
    assert "group_capture_analysis" in names


@pytest.mark.asyncio
async def test_public_tool_surface_remains_stable() -> None:
    server = create_server()

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert names == {
        "analyze_recorded_traffic",
        "charles_status",
        "filter_func",
        "get_capture_analysis_stats",
        "get_recording_snapshot",
        "get_traffic_entry_detail",
        "group_capture_analysis",
        "list_recordings",
        "list_sessions",
        "peek_live_capture",
        "proxy_by_time",
        "query_live_capture_entries",
        "query_recorded_traffic",
        "read_live_capture",
        "reset_environment",
        "start_live_capture",
        "stop_live_capture",
        "throttling",
    }
