from copy import deepcopy

import pytest

import charles_mcp.server as server_module
from charles_mcp.server import create_server


def _tool_result(call_result):
    payload = call_result[1]
    return payload["result"] if isinstance(payload, dict) and "result" in payload else payload


def _entry(
    *,
    host: str = "api.example.com",
    method: str = "GET",
    path: str = "/items",
    start: str = "2026-03-06T10:00:00.000+08:00",
) -> dict:
    return {
        "host": host,
        "method": method,
        "path": path,
        "times": {"start": start},
        "request": {"headers": []},
        "response": {"headers": []},
    }


def _fake_client_class() -> type:
    class FakeClient:
        current_export: list[dict] = []
        history_snapshot: list[dict] = []
        calls: list[str] = []

        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def export_session_json(self) -> list[dict]:
            type(self).calls.append("export")
            return deepcopy(type(self).current_export)

        async def load_latest_session(self, package_dir=None) -> list[dict]:
            type(self).calls.append("history")
            return deepcopy(type(self).history_snapshot)

        async def clear_session(self) -> bool:
            type(self).calls.append("clear")
            return True

        async def start_recording(self) -> bool:
            type(self).calls.append("start")
            return True

        async def stop_recording(self) -> bool:
            type(self).calls.append("stop")
            return True

        def get_full_save_path(self) -> str:
            return "package/fake.chlsj"

    return FakeClient


@pytest.mark.asyncio
async def test_read_live_capture_never_loads_latest_file(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = [_entry(path="/baseline")]

    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(await server.call_tool(
        "start_live_capture",
        {"adopt_existing": True, "include_existing": False},
    ))

    fake_client.current_export = [
        _entry(path="/baseline"),
        _entry(path="/new", start="2026-03-06T10:00:01.000+08:00"),
    ]

    result = _tool_result(await server.call_tool(
        "read_live_capture",
        {"capture_id": started["capture_id"], "cursor": 0},
    ))

    assert "history" not in fake_client.calls
    assert "export" in fake_client.calls
    assert [item["path"] for item in result["items"]] == ["/new"]


@pytest.mark.asyncio
async def test_query_recorded_traffic_only_uses_history_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.history_snapshot = [_entry(path="/history-only")]

    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    result = _tool_result(await server.call_tool("query_recorded_traffic", {}))

    assert fake_client.calls == ["history"]
    assert result["source"] == "history"
    assert result["total_items"] == 1
    assert [item["path"] for item in result["items"]] == ["/history-only"]
