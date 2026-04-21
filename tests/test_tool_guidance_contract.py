import pytest

from charles_mcp.server import create_server


def _assert_contains_keywords(description: str, keywords: tuple[str, ...]) -> None:
    normalized = description.lower()
    for keyword in keywords:
        assert keyword in normalized


@pytest.mark.asyncio
async def test_representative_high_frequency_tools_expose_core_guidance_semantics() -> None:
    server = create_server()
    tools = await server.list_tools()
    by_name = {tool.name: (tool.description or "") for tool in tools}

    expected_keywords: dict[str, tuple[str, ...]] = {
        "start_live_capture": ("capture_id", "reuse"),
        "read_live_capture": ("cursor", "consumes"),
        "peek_live_capture": ("cursor", "does not consume"),
        "query_live_capture_entries": ("summary", "does not advance", "entry_id"),
        "analyze_recorded_traffic": ("history-plane", "recording_path"),
        "get_traffic_entry_detail": ("one confirmed target", "recording_path", "capture_id"),
        "list_recordings": ("history", "recording_path"),
        "reverse_start_live_analysis": ("live_session_id", "reuse"),
        "reverse_query_entries": ("summary-first", "capture_id"),
        "reverse_get_entry_detail": ("candidate selection", "not a bulk-browsing"),
        "reverse_analyze_live_login_flow": ("summary/report", "evidence"),
        "reverse_analyze_live_api_flow": ("summary/report", "evidence"),
        "reverse_analyze_live_signature_flow": ("summary/report", "evidence"),
    }

    for tool_name, keywords in expected_keywords.items():
        assert tool_name in by_name
        _assert_contains_keywords(by_name[tool_name], keywords)
