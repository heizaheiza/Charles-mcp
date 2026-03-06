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
        calls: list[str] = []
        stop_results: list[object] = []

        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def export_session_json(self) -> list[dict]:
            type(self).calls.append("export")
            return deepcopy(type(self).current_export)

        async def clear_session(self) -> bool:
            type(self).calls.append("clear")
            return True

        async def start_recording(self) -> bool:
            type(self).calls.append("start")
            return True

        async def stop_recording(self) -> bool:
            type(self).calls.append("stop")
            if type(self).stop_results:
                result = type(self).stop_results.pop(0)
                if isinstance(result, Exception):
                    raise result
                return bool(result)
            return True

        async def get_info(self):
            type(self).calls.append("info")
            return {"status": "connected"}

    return FakeClient


@pytest.mark.asyncio
async def test_start_live_capture_resets_and_starts_recording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    result = _tool_result(await server.call_tool("start_live_capture", {"reset_session": True}))

    assert result["status"] == "active"
    assert result["managed"] is True
    assert fake_client.calls == ["clear", "start"]


@pytest.mark.asyncio
async def test_peek_live_capture_does_not_advance_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = []
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(await server.call_tool(
        "start_live_capture",
        {"adopt_existing": True, "include_existing": False},
    ))

    fake_client.current_export = [_entry(path="/peeked")]

    peeked = _tool_result(await server.call_tool(
        "peek_live_capture",
        {"capture_id": started["capture_id"], "cursor": 0},
    ))
    read_first = _tool_result(await server.call_tool(
        "read_live_capture",
        {"capture_id": started["capture_id"], "cursor": 0},
    ))
    read_second = _tool_result(await server.call_tool(
        "read_live_capture",
        {"capture_id": started["capture_id"], "cursor": read_first["next_cursor"]},
    ))

    assert [item["path"] for item in peeked["items"]] == ["/peeked"]
    assert [item["path"] for item in read_first["items"]] == ["/peeked"]
    assert read_second["items"] == []


@pytest.mark.asyncio
async def test_stop_live_capture_stops_recording_without_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = [_entry(path="/final")]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(await server.call_tool("start_live_capture", {"reset_session": True}))
    result = _tool_result(await server.call_tool(
        "stop_live_capture",
        {"capture_id": started["capture_id"], "persist": False},
    ))

    assert result["status"] == "stopped"
    assert result["persisted_path"] is None
    assert fake_client.calls == ["clear", "start", "export", "stop"]


@pytest.mark.asyncio
async def test_stop_live_capture_retries_once_before_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = [_entry(path="/final")]
    fake_client.stop_results = [False, True]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(await server.call_tool("start_live_capture", {"reset_session": True}))
    result = _tool_result(
        await server.call_tool(
            "stop_live_capture",
            {"capture_id": started["capture_id"], "persist": False},
        )
    )

    assert result["status"] == "stopped"
    assert "stop_recording_retry_succeeded" in result["warnings"]
    assert result["recoverable"] is False
    assert result["active_capture_preserved"] is False
    assert fake_client.calls == ["clear", "start", "export", "stop", "stop"]


@pytest.mark.asyncio
async def test_stop_live_capture_failure_preserves_active_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = [_entry(path="/final")]
    fake_client.stop_results = [False, False]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(await server.call_tool("start_live_capture", {"reset_session": True}))
    result = _tool_result(
        await server.call_tool(
            "stop_live_capture",
            {"capture_id": started["capture_id"], "persist": False},
        )
    )
    status = _tool_result(await server.call_tool("charles_status", {}))

    assert result["status"] == "stop_failed"
    assert result["recoverable"] is True
    assert result["active_capture_preserved"] is True
    assert result["persisted_path"] is None
    assert "stop_recording_failed_after_retry" in result["warnings"]
    assert status["live_capture"]["active_capture"]["capture_id"] == started["capture_id"]
    assert fake_client.calls == ["clear", "start", "export", "stop", "stop", "info"]
