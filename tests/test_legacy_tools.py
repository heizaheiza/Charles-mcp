import pytest

import charles_mcp.server as server_module
from charles_mcp.client import CharlesClientError
from charles_mcp.server import create_server


def _tool_result(call_result):
    payload = call_result[1]
    return payload["result"] if isinstance(payload, dict) and "result" in payload else payload


def _failing_client_class() -> type:
    class FakeClient:
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

        def get_full_save_path(self) -> str:
            return "package/legacy-failure.chlsj"

        async def record_session(self, duration: int, save_path: str | None = None, progress_callback=None):
            raise CharlesClientError("failed to start Charles recording")

        async def load_latest_session(self, package_dir=None):
            return []

    return FakeClient


@pytest.mark.asyncio
async def test_proxy_by_time_surfaces_recording_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _failing_client_class()
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    result = _tool_result(await server.call_tool("proxy_by_time", {"record_seconds": 1}))

    assert result == [{"error": "failed to start Charles recording"}]
