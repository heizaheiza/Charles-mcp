from copy import deepcopy
import json

import pytest

import charles_mcp.server as server_module
from charles_mcp.server import create_server


def _tool_result(call_result):
    if isinstance(call_result, tuple):
        payload = call_result[1]
        return payload["result"] if isinstance(payload, dict) and "result" in payload else payload
    if isinstance(call_result, list) and call_result:
        return json.loads(call_result[0].text)
    return call_result


def _fake_client_class() -> type:
    class FakeClient:
        current_export: list[dict] = []

        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def connect(self):
            pass

        async def close(self):
            pass

        async def export_session_json(self) -> list[dict]:
            return deepcopy(type(self).current_export)

        async def clear_session(self) -> bool:
            return True

        async def start_recording(self) -> bool:
            return True

        async def get_info(self):
            return {"status": "connected"}

    return FakeClient


@pytest.mark.asyncio
async def test_charles_status_reports_active_live_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(await server.call_tool("start_live_capture", {"reset_session": True}))
    status = _tool_result(await server.call_tool("charles_status", {}))

    assert status["connected"] is True
    assert status["live_capture"]["active_capture"]["capture_id"] == started["capture_id"]
    assert status["live_capture"]["active_capture"]["status"] == "active"
