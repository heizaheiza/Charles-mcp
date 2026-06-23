"""Behavior contract for the since_seconds time-window filter."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import charles_mcp.server as server_module
from charles_mcp.server import create_server


def _tool_result(call_result):
    payload = call_result[1]
    return payload["result"] if isinstance(payload, dict) and "result" in payload else payload


def _api_entry(path: str, *, start: str) -> dict:
    """Synthetic completed API entry with an explicit times.start timestamp."""
    return {
        "status": "COMPLETE",
        "method": "POST",
        "scheme": "https",
        "host": "api.example.com",
        "path": path,
        "query": None,
        "times": {"start": start},
        "durations": {"total": 18},
        "totalSize": 1200,
        "request": {
            "mimeType": "application/json",
            "header": {
                "firstLine": f"POST {path} HTTP/1.1",
                "headers": [{"name": "Content-Type", "value": "application/json"}],
            },
            "sizes": {"body": 32},
            "body": {"text": '{"ok":true}'},
        },
        "response": {
            "status": 200,
            "mimeType": "application/json",
            "header": {
                "firstLine": "HTTP/1.1 200 OK",
                "headers": [{"name": "Content-Type", "value": "application/json"}],
            },
            "sizes": {"body": 16},
            "body": {"text": '{"ok":true}'},
        },
    }


def _iso_utc(dt: datetime) -> str:
    """ISO8601 with milliseconds, always emitted in UTC."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}" + "+00:00"


def _fake_client_class() -> type:
    class FakeClient:
        current_export: list[dict] = []
        calls: list[str] = []

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
            type(self).calls.append("export")
            return deepcopy(type(self).current_export)

        async def clear_session(self) -> bool:
            type(self).calls.append("clear")
            return True

        async def start_recording(self) -> bool:
            type(self).calls.append("start")
            return True

        async def get_info(self):
            return {"status": "connected"}

        def get_full_save_path(self) -> str:
            return "package/fake-since.chlsj"

    return FakeClient


@pytest.mark.asyncio
async def test_query_live_capture_entries_since_seconds_keeps_only_recent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """since_seconds=10 must drop entries older than 10 seconds."""
    fake_client = _fake_client_class()
    now = datetime.now(timezone.utc)
    recent_entry = _api_entry("/api/recent", start=_iso_utc(now - timedelta(seconds=2)))
    stale_entry = _api_entry("/api/stale", start=_iso_utc(now - timedelta(seconds=120)))
    fake_client.current_export = [recent_entry, stale_entry]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(
        await server.call_tool(
            "start_live_capture",
            {"adopt_existing": True, "include_existing": True},
        )
    )

    result = _tool_result(
        await server.call_tool(
            "query_live_capture_entries",
            {
                "capture_id": started["capture_id"],
                "cursor": 0,
                "since_seconds": 10,
            },
        )
    )

    paths = [item["path"] for item in result["items"]]
    assert "/api/recent" in paths
    assert "/api/stale" not in paths


@pytest.mark.asyncio
async def test_query_live_capture_entries_since_seconds_none_matches_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitting since_seconds preserves the legacy behavior of scanning everything."""
    fake_client = _fake_client_class()
    now = datetime.now(timezone.utc)
    recent_entry = _api_entry("/api/recent", start=_iso_utc(now - timedelta(seconds=2)))
    stale_entry = _api_entry("/api/stale", start=_iso_utc(now - timedelta(seconds=3600)))
    fake_client.current_export = [recent_entry, stale_entry]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(
        await server.call_tool(
            "start_live_capture",
            {"adopt_existing": True, "include_existing": True},
        )
    )

    result = _tool_result(
        await server.call_tool(
            "query_live_capture_entries",
            {"capture_id": started["capture_id"], "cursor": 0},
        )
    )

    paths = [item["path"] for item in result["items"]]
    assert "/api/recent" in paths
    assert "/api/stale" in paths


@pytest.mark.asyncio
async def test_query_live_capture_entries_since_seconds_keeps_entries_without_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entries with no parseable timestamp must not be silently dropped.

    Charles may briefly export an in-flight entry whose times.start is
    missing; agents would lose visibility on it if we discarded it.
    """
    fake_client = _fake_client_class()
    now = datetime.now(timezone.utc)
    timeless = _api_entry("/api/no-time", start=_iso_utc(now - timedelta(seconds=5)))
    # Strip the timestamp to simulate an in-flight entry.
    timeless["times"] = {}
    fake_client.current_export = [timeless]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(
        await server.call_tool(
            "start_live_capture",
            {"adopt_existing": True, "include_existing": True},
        )
    )

    result = _tool_result(
        await server.call_tool(
            "query_live_capture_entries",
            {
                "capture_id": started["capture_id"],
                "cursor": 0,
                "since_seconds": 10,
            },
        )
    )

    paths = [item["path"] for item in result["items"]]
    assert "/api/no-time" in paths
