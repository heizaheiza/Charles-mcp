from copy import deepcopy

import pytest

from charles_mcp.config import Config
from charles_mcp.live_state import LiveCaptureManager
from charles_mcp.services.history_capture import RecordingHistoryService
from charles_mcp.services.live_capture import LiveCaptureService


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
            return "package/service-fake.chlsj"

    return FakeClient


@pytest.mark.asyncio
async def test_live_capture_service_reads_incremental_current_session() -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = [_entry(path="/baseline")]
    service = LiveCaptureService(
        config=Config(),
        client_factory=fake_client,
        live_manager=LiveCaptureManager(),
    )

    started = await service.start(adopt_existing=True, include_existing=False)
    fake_client.current_export = [
        _entry(path="/baseline"),
        _entry(path="/live", start="2026-03-06T10:00:01.000+08:00"),
    ]

    result = await service.read(started.capture_id, cursor=0)

    assert "history" not in fake_client.calls
    assert [item["path"] for item in result.items] == ["/live"]


@pytest.mark.asyncio
async def test_recording_history_service_reads_saved_snapshot_only() -> None:
    fake_client = _fake_client_class()
    fake_client.history_snapshot = [_entry(path="/history")]
    service = RecordingHistoryService(config=Config(), client_factory=fake_client)

    result = await service.query_latest_result()

    assert fake_client.calls == ["history"]
    assert result.source == "history"
    assert result.total_items == 1
    assert [item["path"] for item in result.items] == ["/history"]
