from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from charles_mcp.reverse.config import VNextConfig
from charles_mcp.reverse.models import CaptureSourceFormat, CaptureSourceKind
from charles_mcp.reverse.services import IngestService, ReplayService
from charles_mcp.reverse.storage import SQLiteStore
from tests.vnext.test_ingest_and_query import SAMPLE_XML


class _ReplayHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8")
        if '"sign":"valid-signature"' in payload:
            body = b'{"ok":true}'
            self.send_response(200)
        else:
            body = b'{"error":"invalid signature"}'
            self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003
        return


@pytest.mark.asyncio
async def test_replay_service_executes_and_persists_run(tmp_path):
    server = HTTPServer(("127.0.0.1", 0), _ReplayHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        xml_path = tmp_path / "sample.xml"
        sample = (
            SAMPLE_XML.replace('protocol="https"', 'protocol="http"')
            .replace('host="api.example.com"', 'host="127.0.0.1"')
            .replace('port="443"', f'port="{server.server_port}"')
            .replace('actualPort="443"', f'actualPort="{server.server_port}"')
        )
        xml_path.write_text(
            sample,
            encoding="utf-8",
        )

        config = VNextConfig(state_root=tmp_path / "state")
        store = SQLiteStore(config.database_path)
        ingest_service = IngestService(config, store)
        replay_service = ReplayService(config, store)

        imported = ingest_service.import_session(
            path=str(xml_path),
            source_format=CaptureSourceFormat.XML,
            source_kind=CaptureSourceKind.HISTORY_IMPORT,
        )
        entries = store.list_entries(capture_id=imported["capture_id"], limit=10)
        result = await replay_service.replay_entry(
            entry_id=entries[0].entry_id,
            json_overrides={"sign": "valid-signature"},
        )

        assert result["run"]["execution_status"] == "succeeded"
        assert result["response"]["status_code"] == 200
        assert result["run"]["response_body_blob_id"] is not None
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_replay_service_ignores_proxy_env(tmp_path, monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _ReplayHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")

        xml_path = tmp_path / "sample.xml"
        sample = (
            SAMPLE_XML.replace('protocol="https"', 'protocol="http"')
            .replace('host="api.example.com"', 'host="127.0.0.1"')
            .replace('port="443"', f'port="{server.server_port}"')
            .replace('actualPort="443"', f'actualPort="{server.server_port}"')
        )
        xml_path.write_text(sample, encoding="utf-8")

        config = VNextConfig(state_root=tmp_path / "state")
        store = SQLiteStore(config.database_path)
        ingest_service = IngestService(config, store)
        replay_service = ReplayService(config, store)

        imported = ingest_service.import_session(
            path=str(xml_path),
            source_format=CaptureSourceFormat.XML,
            source_kind=CaptureSourceKind.HISTORY_IMPORT,
        )
        entries = store.list_entries(capture_id=imported["capture_id"], limit=10)
        result = await replay_service.replay_entry(
            entry_id=entries[0].entry_id,
            json_overrides={"sign": "valid-signature"},
        )

        assert result["response"]["status_code"] == 200
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_replay_service_uses_explicit_proxy_when_requested(tmp_path, monkeypatch):
    xml_path = tmp_path / "sample.xml"
    xml_path.write_text(SAMPLE_XML, encoding="utf-8")

    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    replay_service = ReplayService(config, store)

    imported = ingest_service.import_session(
        path=str(xml_path),
        source_format=CaptureSourceFormat.XML,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )
    entry_id = store.list_entries(capture_id=imported["capture_id"], limit=1)[0].entry_id
    observed: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            observed["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, headers=None, content=None):
            observed["request"] = {
                "method": method,
                "url": url,
                "headers": headers,
                "content": content,
            }
            return httpx.Response(
                200,
                content=b'{"ok":true}',
                headers={"Content-Type": "application/json"},
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr("charles_mcp.reverse.services.replay_service.httpx.AsyncClient", FakeAsyncClient)

    result = await replay_service.replay_entry(
        entry_id=entry_id,
        json_overrides={"sign": "valid-signature"},
        use_proxy=True,
    )

    assert result["response"]["status_code"] == 200
    assert observed["client_kwargs"]["proxy"] == config.charles_proxy_url
    assert observed["client_kwargs"]["trust_env"] is False

