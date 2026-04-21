from charles_mcp.reverse.config import VNextConfig
from charles_mcp.reverse.models import CaptureSourceFormat, CaptureSourceKind
from charles_mcp.reverse.services import IngestService
from charles_mcp.reverse.storage import SQLiteStore
import json
import zipfile


def test_native_import_parses_zip_archive_directly(tmp_path):
    native_path = tmp_path / "capture.chls"
    with zipfile.ZipFile(native_path, "w") as zf:
        zf.writestr(
            "0-meta.json",
            json.dumps(
                {
                    "status": "COMPLETE",
                    "method": "POST",
                    "protocolVersion": "HTTP/1.1",
                    "scheme": "http",
                    "host": "127.0.0.1",
                    "port": 8080,
                    "actualPort": 8080,
                    "path": "/login",
                    "query": None,
                    "remoteAddress": "127.0.0.1/127.0.0.1",
                    "clientAddress": "/127.0.0.1",
                    "times": {"start": "2026-04-14T00:00:00+08:00", "end": "2026-04-14T00:00:01+08:00"},
                    "durations": {"total": 1},
                    "totalSize": 100,
                    "request": {
                        "sizes": {"headers": 10, "body": 17},
                        "mimeType": "application/json",
                        "charset": "utf-8",
                        "contentEncoding": None,
                        "header": {
                            "firstLine": "POST /login HTTP/1.1",
                            "headers": [{"name": "Content-Type", "value": "application/json"}],
                        },
                    },
                    "response": {
                        "status": 200,
                        "sizes": {"headers": 10, "body": 14},
                        "mimeType": "application/json",
                        "charset": "utf-8",
                        "contentEncoding": None,
                        "header": {
                            "firstLine": "HTTP/1.1 200 OK",
                            "headers": [{"name": "Content-Type", "value": "application/json"}],
                        },
                    },
                }
            ),
        )
        zf.writestr("0-req.json", '{"user":"alice"}')
        zf.writestr("0-res.json", '{"ok":true}')

    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    service = IngestService(config, store)

    result = service.import_session(
        path=str(native_path),
        source_format=CaptureSourceFormat.NATIVE,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )

    snapshot = store.get_entry_snapshot(store.list_entries(capture_id=result["capture_id"], limit=1)[0].entry_id)
    assert result["entry_count"] == 1
    assert snapshot["request_body_blob"].raw_text == '{"user":"alice"}'
    assert snapshot["response_body_blob"].raw_text == '{"ok":true}'
    assert snapshot["entry"].timing_summary["start_time_ms"] == 1776096000000
    assert snapshot["entry"].timing_summary["end_time_ms"] == 1776096001000


def test_native_import_parses_start_time_when_start_millis_is_missing(tmp_path):
    native_path = tmp_path / "capture-missing-millis.chls"
    with zipfile.ZipFile(native_path, "w") as zf:
        zf.writestr(
            "0-meta.json",
            json.dumps(
                {
                    "status": "COMPLETE",
                    "method": "GET",
                    "protocolVersion": "HTTP/1.1",
                    "scheme": "https",
                    "host": "api.example.com",
                    "path": "/orders",
                    "times": {
                        "start": "2026-04-14T00:00:00.123Z",
                        "end": "2026-04-14T00:00:01.456Z",
                    },
                    "request": {
                        "sizes": {"headers": 10},
                        "header": {"firstLine": "GET /orders HTTP/1.1", "headers": []},
                    },
                    "response": {
                        "status": 200,
                        "sizes": {"headers": 10},
                        "header": {"firstLine": "HTTP/1.1 200 OK", "headers": []},
                    },
                }
            ),
        )

    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    service = IngestService(config, store)

    result = service.import_session(
        path=str(native_path),
        source_format=CaptureSourceFormat.NATIVE,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )

    entry = store.list_entries(capture_id=result["capture_id"], limit=1)[0]
    snapshot = store.get_entry_snapshot(entry.entry_id)

    assert snapshot is not None
    assert snapshot["entry"].timing_summary["start_time_ms"] == 1776124800123
    assert snapshot["entry"].timing_summary["end_time_ms"] == 1776124801456


def test_native_import_uses_charles_convert_bridge(tmp_path, monkeypatch):
    native_path = tmp_path / "capture.chls"
    native_path.write_bytes(b"native-session")
    converted_xml_path = tmp_path / "converted.xml"
    converted_xml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<charles-session>
  <transaction method="GET" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/ping" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-13T12:00:00Z" startTimeMillis="1713000000000" responseTime="2026-04-13T12:00:01Z" responseTimeMillis="1713000001000" endTime="2026-04-13T12:00:01Z" endTimeMillis="1713000001000">
    <request headers="true" body="false">
      <headers><first-line>GET /ping HTTP/1.1</first-line></headers>
    </request>
    <response status="200" headers="true" body="false" mime-type="application/json">
      <headers><first-line>HTTP/1.1 200 OK</first-line></headers>
    </response>
  </transaction>
</charles-session>
""",
        encoding="utf-8",
    )

    calls: list[tuple[str, str, str]] = []

    def fake_convert_native_session_to_xml(*, charles_cli_path: str, source_path: str, target_path: str):
        calls.append((charles_cli_path, source_path, target_path))
        return converted_xml_path

    monkeypatch.setattr(
        "charles_mcp.reverse.services.ingest_service.convert_native_session_to_xml",
        fake_convert_native_session_to_xml,
    )

    config = VNextConfig(state_root=tmp_path / "state")
    config.charles_cli_path = "C:/Program Files/Charles/Charles.exe"
    store = SQLiteStore(config.database_path)
    service = IngestService(config, store)

    result = service.import_session(
        path=str(native_path),
        source_format=CaptureSourceFormat.NATIVE,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )

    assert result["entry_count"] == 1
    assert "native_session_converted_to_xml" in result["warnings"]
    assert calls[0][0].endswith("Charles.exe")

