from pathlib import Path

import pytest
from defusedxml.common import DefusedXmlException

import charles_mcp.reverse.storage.sqlite_store as sqlite_store_module
from charles_mcp.reverse.config import VNextConfig
from charles_mcp.reverse.models import CaptureSourceFormat, CaptureSourceKind
from charles_mcp.reverse.services import DecodeService, IngestService, QueryService
from charles_mcp.reverse.storage import SQLiteStore


SAMPLE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<charles-session>
  <transaction method="POST" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/v1/login" query="ts=123" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-13T12:00:00Z" startTimeMillis="1713000000000" responseTime="2026-04-13T12:00:01Z" responseTimeMillis="1713000001000" endTime="2026-04-13T12:00:01Z" endTimeMillis="1713000001000">
    <request headers="true" body="true" charset="utf-8">
      <headers>
        <first-line>POST /v1/login?ts=123 HTTP/1.1</first-line>
        <header><name>Content-Type</name><value>application/json</value></header>
        <header><name>Cookie</name><value>session=abc; csrftoken=def</value></header>
      </headers>
      <body encoding="plain">{&quot;user&quot;:&quot;alice&quot;,&quot;sign&quot;:&quot;abc123xyz&quot;}</body>
    </request>
    <response status="200" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers>
        <first-line>HTTP/1.1 200 OK</first-line>
        <header><name>Content-Type</name><value>application/json</value></header>
      </headers>
      <body encoding="plain">{&quot;token&quot;:&quot;abc&quot;}</body>
    </response>
  </transaction>
  <transaction method="POST" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/v1/login" query="ts=124" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-13T12:00:02Z" startTimeMillis="1713000002000" responseTime="2026-04-13T12:00:03Z" responseTimeMillis="1713000003000" endTime="2026-04-13T12:00:03Z" endTimeMillis="1713000003000">
    <request headers="true" body="true" charset="utf-8">
      <headers>
        <first-line>POST /v1/login?ts=124 HTTP/1.1</first-line>
        <header><name>Content-Type</name><value>application/json</value></header>
      </headers>
      <body encoding="plain">{&quot;user&quot;:&quot;alice&quot;,&quot;sign&quot;:&quot;other987&quot;}</body>
    </request>
    <response status="401" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers>
        <first-line>HTTP/1.1 401 Unauthorized</first-line>
        <header><name>Content-Type</name><value>application/json</value></header>
      </headers>
      <body encoding="plain">{&quot;error&quot;:&quot;invalid signature&quot;}</body>
    </response>
  </transaction>
</charles-session>
"""


def _build_services(tmp_path: Path):
    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    return (
        config,
        store,
        IngestService(config, store),
        QueryService(store),
        DecodeService(store),
    )


def test_xml_ingest_query_decode_and_signature_candidates(tmp_path):
    xml_path = tmp_path / "sample.xml"
    xml_path.write_text(SAMPLE_XML, encoding="utf-8")

    _, store, ingest_service, query_service, decode_service = _build_services(tmp_path)
    imported = ingest_service.import_session(
        path=str(xml_path),
        source_format=CaptureSourceFormat.XML,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )

    captures = query_service.list_captures(limit=10)
    queried = query_service.query_entries(capture_id=imported["capture_id"], limit=10)
    entry_id = queried["items"][0]["entry_id"]
    detail = query_service.get_entry_detail(entry_id=entry_id)
    decoded = decode_service.decode_entry_body(entry_id=entry_id, side="response")
    candidate_scan = query_service.discover_signature_candidates(
        entry_ids=[item["entry_id"] for item in queried["items"]]
    )
    findings = query_service.list_findings()

    assert imported["entry_count"] == 2
    assert len(captures) == 1
    assert queried["returned"] == 2
    assert detail["request"]["cookies"]["session"] == "abc"
    assert decoded["artifact_type"] == "json"
    assert candidate_scan["candidates"][0]["field"] == "json.sign"
    assert any(item["finding_type"] == "signature_candidate" for item in findings)


def test_xml_ingest_rejects_dtd_entities(tmp_path):
    xml_path = tmp_path / "malicious.xml"
    xml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE charles-session [
  <!ENTITY boom "boom">
]>
<charles-session>
  <transaction method="GET" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" path="/ping">
    <request headers="true" body="false"><headers><first-line>GET /ping HTTP/1.1</first-line></headers></request>
    <response status="200" headers="true" body="true" mime-type="application/json">
      <headers><first-line>HTTP/1.1 200 OK</first-line></headers>
      <body encoding="plain">&boom;</body>
    </response>
  </transaction>
</charles-session>
""",
        encoding="utf-8",
    )

    _, _, ingest_service, _, _ = _build_services(tmp_path)

    with pytest.raises(DefusedXmlException):
        ingest_service.import_session(
            path=str(xml_path),
            source_format=CaptureSourceFormat.XML,
            source_kind=CaptureSourceKind.HISTORY_IMPORT,
        )


def test_ingest_reuses_single_sqlite_connection(tmp_path, monkeypatch):
    xml_path = tmp_path / "sample.xml"
    xml_path.write_text(SAMPLE_XML, encoding="utf-8")

    connect_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    original_connect = sqlite_store_module.sqlite3.connect

    def tracking_connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_store_module.sqlite3, "connect", tracking_connect)

    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)

    imported = ingest_service.import_session(
        path=str(xml_path),
        source_format=CaptureSourceFormat.XML,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )
    entries = store.list_entries(capture_id=imported["capture_id"], limit=10)

    assert len(entries) == 2
    assert len(connect_calls) == 1

