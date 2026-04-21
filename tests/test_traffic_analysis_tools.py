from copy import deepcopy
import json
from pathlib import Path

import pytest

import charles_mcp.server as server_module
from charles_mcp.config import Config
from charles_mcp.server import create_server


def _tool_result(call_result):
    payload = call_result[1]
    return payload["result"] if isinstance(payload, dict) and "result" in payload else payload


def _api_entry(path: str = "/api/login") -> dict:
    return {
        "status": "COMPLETE",
        "method": "POST",
        "scheme": "https",
        "host": "api.example.com",
        "path": path,
        "query": "device=ios",
        "times": {"start": "2026-03-06T10:00:00.000+08:00"},
        "durations": {"total": 18},
        "totalSize": 1200,
        "request": {
            "mimeType": "application/json",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": 64},
            "header": {
                "firstLine": f"POST {path} HTTP/1.1",
                "headers": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Authorization", "value": "Bearer live-secret"},
                ],
            },
            "body": {"text": '{"username":"alice","password":"super-secret"}'},
        },
        "response": {
            "status": 200,
            "mimeType": "application/json",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": 80},
            "header": {
                "firstLine": "HTTP/1.1 200 OK",
                "headers": [{"name": "Content-Type", "value": "application/json"}],
            },
            "body": {"text": '{"ok":true,"access_token":"token-value"}'},
        },
    }


def _image_entry(
    path: str = "/assets/logo.png",
    start: str = "2026-03-06T10:00:01.000+08:00",
) -> dict:
    return {
        "status": "COMPLETE",
        "method": "GET",
        "scheme": "https",
        "host": "static.example.com",
        "path": path,
        "query": None,
        "times": {"start": start},
        "durations": {"total": 8},
        "totalSize": 24576,
        "request": {
            "mimeType": None,
            "charset": None,
            "contentEncoding": None,
            "sizes": {"body": 0},
            "header": {"firstLine": f"GET {path} HTTP/1.1", "headers": []},
        },
        "response": {
            "status": 200,
            "mimeType": "image/png",
            "charset": None,
            "contentEncoding": None,
            "sizes": {"body": 24576},
            "header": {
                "firstLine": "HTTP/1.1 200 OK",
                "headers": [{"name": "Content-Type", "value": "image/png"}],
            },
        },
    }


def _multipart_entry() -> dict:
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="meta"\r\n'
        "Content-Type: application/json\r\n\r\n"
        '{"title":"hello","token":"super-token"}\r\n'
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="report.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "report body\r\n"
        f"--{boundary}--\r\n"
    )
    return {
        "status": "COMPLETE",
        "method": "POST",
        "scheme": "https",
        "host": "upload.example.com",
        "path": "/api/upload",
        "query": None,
        "times": {"start": "2026-03-06T10:00:03.000+08:00"},
        "durations": {"total": 44},
        "totalSize": 4096,
        "request": {
            "mimeType": f"multipart/form-data; boundary={boundary}",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": len(body)},
            "header": {
                "firstLine": "POST /api/upload HTTP/1.1",
                "headers": [
                    {
                        "name": "Content-Type",
                        "value": f"multipart/form-data; boundary={boundary}",
                    }
                ],
            },
            "body": {"text": body},
        },
        "response": {
            "status": 201,
            "mimeType": "application/json",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": 32},
            "header": {
                "firstLine": "HTTP/1.1 201 Created",
                "headers": [{"name": "Content-Type", "value": "application/json"}],
            },
            "body": {"text": '{"ok":true}'},
        },
    }


def _long_text_entry(*, path: str = "/api/search", marker: str = "secret-token") -> dict:
    request_body = ("A" * 200) + marker
    response_body = ("B" * 200) + marker
    return {
        "status": "COMPLETE",
        "method": "POST",
        "scheme": "https",
        "host": "api.example.com",
        "path": path,
        "query": None,
        "times": {"start": "2026-03-06T10:00:04.000+08:00"},
        "durations": {"total": 22},
        "totalSize": len(request_body) + len(response_body),
        "request": {
            "mimeType": "text/plain",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": len(request_body)},
            "header": {
                "firstLine": f"POST {path} HTTP/1.1",
                "headers": [{"name": "Content-Type", "value": "text/plain"}],
            },
            "body": {"text": request_body},
        },
        "response": {
            "status": 200,
            "mimeType": "text/plain",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": len(response_body)},
            "header": {
                "firstLine": "HTTP/1.1 200 OK",
                "headers": [{"name": "Content-Type", "value": "text/plain"}],
            },
            "body": {"text": response_body},
        },
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

        async def connect(self):
            pass

        async def close(self):
            pass

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

        async def get_info(self):
            return {"status": "connected"}

        def get_full_save_path(self) -> str:
            return "package/analysis-fake.chlsj"

    return FakeClient


@pytest.mark.asyncio
async def test_analyze_recorded_traffic_returns_summary_and_filters_static_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.history_snapshot = [_api_entry(), _image_entry()]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    result = _tool_result(await server.call_tool("analyze_recorded_traffic", {}))

    assert fake_client.calls == ["history"]
    assert result["source"] == "history"
    assert result["matched_count"] == 1
    assert result["filtered_out_count"] == 1
    assert result["filtered_out_by_class"]["static_asset"] == 1
    assert result["items"][0]["path"] == "/api/login"
    assert result["items"][0]["resource_class"] == "api_candidate"
    assert result["items"][0]["request_header_highlights"]["authorization"] == "Bearer live-secret"
    assert result["items"][0]["recording_path"]


@pytest.mark.asyncio
async def test_query_live_capture_entries_prefers_export_and_exposes_next_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = [_api_entry("/api/bootstrap")]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(
        await server.call_tool(
            "start_live_capture",
            {"adopt_existing": True, "include_existing": False},
        )
    )

    fake_client.current_export = [_api_entry("/api/bootstrap"), _api_entry("/api/profile")]
    result = _tool_result(
        await server.call_tool(
            "query_live_capture_entries",
            {"capture_id": started["capture_id"], "cursor": 0},
        )
    )

    assert "history" not in fake_client.calls
    assert result["source"] == "live"
    assert result["next_cursor"] >= 1
    assert result["items"][0]["path"] == "/api/profile"


@pytest.mark.asyncio
async def test_get_traffic_entry_detail_returns_history_detail_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.history_snapshot = [_api_entry()]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    summary = _tool_result(await server.call_tool("analyze_recorded_traffic", {}))
    entry_id = summary["items"][0]["entry_id"]

    detail = _tool_result(
        await server.call_tool(
            "get_traffic_entry_detail",
            {"source": "history", "entry_id": entry_id},
        )
    )

    assert detail["source"] == "history"
    assert detail["entry_id"] == entry_id
    assert detail["detail"]["entry"]["request"]["body"]["kind"] == "json"
    req_headers = detail["detail"]["entry"]["request"]["headers"]
    auth = next(h for h in req_headers if h["name"] == "Authorization")
    assert auth["value"] == "Bearer live-secret"
    assert "header_map" not in detail["detail"]["entry"]["request"]
    assert detail["detail"]["entry"]["response"]["body"]["preview_text"] == '{"ok":true,"access_token":"token-value"}'


@pytest.mark.asyncio
async def test_analyze_recorded_traffic_returns_consistent_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.history_snapshot = [_api_entry()]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    result_a = _tool_result(await server.call_tool("analyze_recorded_traffic", {}))
    result_b = _tool_result(await server.call_tool("analyze_recorded_traffic", {}))

    assert result_a["items"] == result_b["items"]


@pytest.mark.asyncio
async def test_query_live_capture_entries_returns_full_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = [_api_entry("/api/bootstrap")]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(
        await server.call_tool(
            "start_live_capture",
            {"adopt_existing": True, "include_existing": False},
        )
    )

    fake_client.current_export = [_api_entry("/api/bootstrap"), _api_entry("/api/profile")]

    result = _tool_result(
        await server.call_tool(
            "query_live_capture_entries",
            {"capture_id": started["capture_id"], "cursor": 0},
        )
    )

    assert result["items"][0]["request_header_highlights"]["authorization"] == "Bearer live-secret"


@pytest.mark.asyncio
async def test_query_live_capture_entries_honors_live_scan_limit_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.current_export = [_api_entry("/api/bootstrap")]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    started = _tool_result(
        await server.call_tool(
            "start_live_capture",
            {"adopt_existing": True, "include_existing": False},
        )
    )

    noisy_entries = [
        _image_entry(
            path=f"/assets/{index}.png",
            start=f"2026-03-06T10:01:{index:02d}.000+08:00",
        )
        for index in range(60)
    ]
    fake_client.current_export = [_api_entry("/api/bootstrap"), *noisy_entries, _api_entry("/api/tail")]

    result = _tool_result(
        await server.call_tool(
            "query_live_capture_entries",
            {
                "capture_id": started["capture_id"],
                "cursor": 0,
                "scan_limit": 500,
                "max_items": 10,
            },
        )
    )

    assert result["total_items"] == 61
    assert result["scanned_count"] == 61
    assert result["matched_count"] == 1
    assert result["items"][0]["path"] == "/api/tail"


@pytest.mark.asyncio
async def test_analyze_recorded_traffic_matches_body_text_beyond_preview_window(
    tmp_path: Path,
) -> None:
    config = Config(base_dir=str(tmp_path))
    recording_path = tmp_path / "package" / "body-filter.chlsj"
    recording_path.parent.mkdir(parents=True, exist_ok=True)
    recording_path.write_text(json.dumps([_long_text_entry()]), encoding="utf-8")

    server = create_server(config)
    result = _tool_result(
        await server.call_tool(
            "analyze_recorded_traffic",
            {
                "recording_path": str(recording_path),
                "request_body_contains": "secret-token",
                "max_preview_chars": 64,
            },
        )
    )

    assert result["matched_count"] == 1
    assert result["items"][0]["path"] == "/api/search"


@pytest.mark.asyncio
async def test_analyze_recorded_traffic_supports_structured_filters_and_detail_full_body(
    tmp_path: Path,
) -> None:
    config = Config(base_dir=str(tmp_path))
    recording_path = tmp_path / "package" / "manual.chlsj"
    recording_path.parent.mkdir(parents=True, exist_ok=True)
    recording_path.write_text(
        json.dumps([_api_entry("/api/login"), _multipart_entry()]),
        encoding="utf-8",
    )

    server = create_server(config)
    summary = _tool_result(
        await server.call_tool(
            "analyze_recorded_traffic",
            {
                "recording_path": str(recording_path),
                "method_in": ["POST"],
                "status_in": [201],
                "request_content_type": "multipart/form-data",
                "response_content_type": "application/json",
            },
        )
    )

    assert summary["matched_count"] == 1
    assert summary["items"][0]["path"] == "/api/upload"

    detail = _tool_result(
        await server.call_tool(
            "get_traffic_entry_detail",
            {
                "source": "history",
                "entry_id": summary["items"][0]["entry_id"],
                "include_full_body": True,
            },
        )
    )

    request_body = detail["detail"]["entry"]["request"]["body"]
    assert detail["detail"]["entry"]["recording_path"] == str(recording_path)
    assert request_body["kind"] == "multipart"
    assert len(request_body["multipart_summary"]) == 2
    assert request_body["multipart_summary"][1]["filename"] == "report.txt"
    assert detail["detail"]["raw_body_included"] is True


@pytest.mark.asyncio
async def test_get_capture_analysis_stats_reports_classified_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.history_snapshot = [_api_entry(), _image_entry()]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    stats = _tool_result(
        await server.call_tool(
            "get_capture_analysis_stats",
            {"source": "history", "preset": "api_focus"},
        )
    )

    assert stats["source"] == "history"
    assert stats["preset"] == "api_focus"
    assert stats["total_items"] == 2
    assert stats["classified_counts"]["api_candidate"] == 1
    assert stats["classified_counts"]["static_asset"] == 1


@pytest.mark.asyncio
async def test_group_capture_analysis_groups_history_by_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.history_snapshot = [
        _api_entry("/api/login"),
        _api_entry("/api/profile"),
        _multipart_entry(),
        _image_entry(),
    ]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    result = _tool_result(
        await server.call_tool(
            "group_capture_analysis",
            {
                "source": "history",
                "group_by": "host",
                "preset": "api_focus",
                "method_in": ["POST"],
                "max_groups": 5,
            },
        )
    )

    assert result["source"] == "history"
    assert result["group_by"] == "host"
    assert result["matched_count"] == 3
    assert result["filtered_out_by_class"]["static_asset"] == 1
    assert result["groups"][0]["group_value"] == "api.example.com"
    assert result["groups"][0]["count"] == 2
    assert "/api/login" in result["groups"][0]["sample_paths"]
    assert result["groups"][1]["group_value"] == "upload.example.com"


@pytest.mark.asyncio
async def test_group_capture_analysis_supports_composite_host_path_grouping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _fake_client_class()
    fake_client.history_snapshot = [
        _api_entry("/api/login"),
        _api_entry("/api/login"),
        _api_entry("/api/profile"),
        _multipart_entry(),
    ]
    monkeypatch.setattr(server_module, "CharlesClient", fake_client)

    server = create_server()
    result = _tool_result(
        await server.call_tool(
            "group_capture_analysis",
            {
                "source": "history",
                "group_by": "host_path",
                "preset": "api_focus",
                "method_in": ["POST"],
                "max_groups": 5,
            },
        )
    )

    assert result["group_by"] == "host_path"
    assert result["groups"][0]["group_value"] == "api.example.com /api/login"
    assert result["groups"][0]["count"] == 2
    assert result["groups"][0]["sample_paths"] == ["/api/login"]
