from pathlib import Path

import pytest

from charles_mcp.reverse.config import VNextConfig
from charles_mcp.reverse.models import CaptureSourceFormat
from charles_mcp.reverse.services import (
    DecodeService,
    IngestService,
    LiveAnalysisService,
    QueryService,
    ReplayService,
    WorkflowService,
)
from charles_mcp.reverse.storage import SQLiteStore
from tests.vnext.test_live_analysis_service import _FakeControlService, _build_snapshot


def _build_login_workflow_snapshot() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?><charles-session>
  <transaction method="GET" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/json" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:00:01Z" startTimeMillis="1713000000001" responseTime="2026-04-14T12:00:01Z" responseTimeMillis="1713000000001" endTime="2026-04-14T12:00:01Z" endTimeMillis="1713000000001">
    <request headers="true" body="false">
      <headers><first-line>GET /json HTTP/1.1</first-line></headers>
    </request>
    <response status="200" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 200 OK</first-line></headers>
      <body encoding="plain">{"path":"/json"}</body>
    </response>
  </transaction>
  <transaction method="POST" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/login" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:00:02Z" startTimeMillis="1713000000002" responseTime="2026-04-14T12:00:02Z" responseTimeMillis="1713000000002" endTime="2026-04-14T12:00:02Z" endTimeMillis="1713000000002">
    <request headers="true" body="true" charset="utf-8">
      <headers><first-line>POST /login HTTP/1.1</first-line><header><name>Content-Type</name><value>application/json</value></header></headers>
      <body encoding="plain">{"user":"alice","ts":"601","sign":"bad-1"}</body>
    </request>
    <response status="401" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 401 Unauthorized</first-line></headers>
      <body encoding="plain">{"status":401}</body>
    </response>
  </transaction>
  <transaction method="POST" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/login" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:00:03Z" startTimeMillis="1713000000003" responseTime="2026-04-14T12:00:03Z" responseTimeMillis="1713000000003" endTime="2026-04-14T12:00:03Z" endTimeMillis="1713000000003">
    <request headers="true" body="true" charset="utf-8">
      <headers><first-line>POST /login HTTP/1.1</first-line><header><name>Content-Type</name><value>application/json</value></header></headers>
      <body encoding="plain">{"user":"alice","ts":"602","sign":"bad-2"}</body>
    </request>
    <response status="401" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 401 Unauthorized</first-line></headers>
      <body encoding="plain">{"status":401}</body>
    </response>
  </transaction>
</charles-session>"""


def _build_api_workflow_snapshot() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?><charles-session>
  <transaction method="GET" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/health" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:10:01Z" startTimeMillis="1713000010001" responseTime="2026-04-14T12:10:01Z" responseTimeMillis="1713000010001" endTime="2026-04-14T12:10:01Z" endTimeMillis="1713000010001">
    <request headers="true" body="false">
      <headers><first-line>GET /health HTTP/1.1</first-line></headers>
    </request>
    <response status="200" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 200 OK</first-line></headers>
      <body encoding="plain">{"ok":true}</body>
    </response>
  </transaction>
  <transaction method="POST" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/api/orders/create" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:10:02Z" startTimeMillis="1713000010002" responseTime="2026-04-14T12:10:02Z" responseTimeMillis="1713000010002" endTime="2026-04-14T12:10:02Z" endTimeMillis="1713000010002">
    <request headers="true" body="true" charset="utf-8">
      <headers><first-line>POST /api/orders/create HTTP/1.1</first-line><header><name>Content-Type</name><value>application/json</value></header></headers>
      <body encoding="plain">{"sku":"abc","quantity":1}</body>
    </request>
    <response status="201" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 201 Created</first-line></headers>
      <body encoding="plain">{"order_id":"o-1"}</body>
    </response>
  </transaction>
  <transaction method="POST" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/api/secure/submit" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:10:03Z" startTimeMillis="1713000010003" responseTime="2026-04-14T12:10:03Z" responseTimeMillis="1713000010003" endTime="2026-04-14T12:10:03Z" endTimeMillis="1713000010003">
    <request headers="true" body="true" charset="utf-8">
      <headers><first-line>POST /api/secure/submit HTTP/1.1</first-line><header><name>Content-Type</name><value>application/json</value></header></headers>
      <body encoding="plain">{"user":"alice","ts":"811","sign":"sig-a"}</body>
    </request>
    <response status="403" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 403 Forbidden</first-line></headers>
      <body encoding="plain">{"status":403}</body>
    </response>
  </transaction>
</charles-session>"""


def _build_signature_workflow_snapshot() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?><charles-session>
  <transaction method="POST" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/api/secure/submit" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:20:01Z" startTimeMillis="1713000020001" responseTime="2026-04-14T12:20:01Z" responseTimeMillis="1713000020001" endTime="2026-04-14T12:20:01Z" endTimeMillis="1713000020001">
    <request headers="true" body="true" charset="utf-8">
      <headers><first-line>POST /api/secure/submit HTTP/1.1</first-line><header><name>Content-Type</name><value>application/json</value></header></headers>
      <body encoding="plain">{"user":"alice","ts":"801","sign":"sig-a"}</body>
    </request>
    <response status="401" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 401 Unauthorized</first-line></headers>
      <body encoding="plain">{"status":401}</body>
    </response>
  </transaction>
  <transaction method="POST" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/api/secure/submit" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:20:02Z" startTimeMillis="1713000020002" responseTime="2026-04-14T12:20:02Z" responseTimeMillis="1713000020002" endTime="2026-04-14T12:20:02Z" endTimeMillis="1713000020002">
    <request headers="true" body="true" charset="utf-8">
      <headers><first-line>POST /api/secure/submit HTTP/1.1</first-line><header><name>Content-Type</name><value>application/json</value></header></headers>
      <body encoding="plain">{"user":"alice","ts":"802","sign":"sig-b"}</body>
    </request>
    <response status="403" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 403 Forbidden</first-line></headers>
      <body encoding="plain">{"status":403}</body>
    </response>
  </transaction>
</charles-session>"""


@pytest.mark.asyncio
async def test_workflow_service_analyzes_live_login_flow(tmp_path: Path):
    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    query_service = QueryService(store)
    decode_service = DecodeService(store)
    replay_service = ReplayService(config, store)
    control = _FakeControlService(
        [
            _build_snapshot(),
            _build_login_workflow_snapshot(),
        ],
        recording=True,
    )
    live_service = LiveAnalysisService(
        control_service=control,  # type: ignore[arg-type]
        ingest_service=ingest_service,
        query_service=query_service,
        temp_dir=config.temp_dir,
    )
    workflow_service = WorkflowService(
        live_service=live_service,
        query_service=query_service,
        decode_service=decode_service,
        replay_service=replay_service,
    )

    started = await live_service.start(reset_session=False, start_recording_if_stopped=False)
    result = await workflow_service.analyze_live_login_flow(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        path_keywords=["login"],
        limit=20,
        advance=True,
        decode_bodies=True,
        run_replay=False,
    )

    assert result["analysis_status"] == "ok"
    assert result["summary"]["selected_entry_id"] is not None
    assert result["summary"]["login_candidate_count"] >= 1
    assert result["report"]["selected_request"]["path"] == "/login"
    assert result["report"]["decoded_observations"]
    assert result["report"]["signature_analysis"]["candidate_count"] >= 1
    assert result["summary"]["mutation_plan_overview"]["candidate_target_count"] >= 1
    assert "Prioritize" in result["report"]["mutation_strategy"]
    assert result["evidence"]["selected_entry_detail"]["entry"]["path"] == "/login"
    assert result["evidence"]["decoded_response"]["artifact_type"] == "json"
    assert result["evidence"]["mutation_plan"]["baseline_entry_id"] == result["summary"]["selected_entry_id"]
    variant_ids = {variant["variant_id"] for variant in result["evidence"]["mutation_plan"]["variants"]}
    assert set(result["evidence"]["mutation_plan"]["execution_order"]).issubset(variant_ids)


@pytest.mark.asyncio
async def test_workflow_service_analyzes_live_api_flow(tmp_path: Path):
    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    query_service = QueryService(store)
    decode_service = DecodeService(store)
    replay_service = ReplayService(config, store)
    control = _FakeControlService(
        [
            _build_snapshot(),
            _build_api_workflow_snapshot(),
        ],
        recording=True,
    )
    live_service = LiveAnalysisService(
        control_service=control,  # type: ignore[arg-type]
        ingest_service=ingest_service,
        query_service=query_service,
        temp_dir=config.temp_dir,
    )
    workflow_service = WorkflowService(
        live_service=live_service,
        query_service=query_service,
        decode_service=decode_service,
        replay_service=replay_service,
    )

    started = await live_service.start(reset_session=False, start_recording_if_stopped=False)
    result = await workflow_service.analyze_live_api_flow(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        path_keywords=["api", "orders"],
        limit=20,
        advance=True,
        decode_bodies=True,
        run_replay=False,
    )

    assert result["analysis_status"] == "ok"
    assert result["summary"]["selected_entry_id"] is not None
    assert result["report"]["selected_request"]["path"] == "/api/orders/create"
    assert "API-like" in result["report"]["overview"]
    assert result["evidence"]["selected_entry_detail"]["entry"]["method"] == "POST"
    assert result["summary"]["mutation_plan_overview"]["candidate_target_count"] >= 1
    top_target = result["evidence"]["mutation_plan"]["targets"][0]
    assert "sign" not in top_target["field"]


@pytest.mark.asyncio
async def test_workflow_service_analyzes_live_signature_flow(tmp_path: Path):
    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    query_service = QueryService(store)
    decode_service = DecodeService(store)
    replay_service = ReplayService(config, store)
    control = _FakeControlService(
        [
            _build_snapshot(),
            _build_signature_workflow_snapshot(),
        ],
        recording=True,
    )
    live_service = LiveAnalysisService(
        control_service=control,  # type: ignore[arg-type]
        ingest_service=ingest_service,
        query_service=query_service,
        temp_dir=config.temp_dir,
    )
    workflow_service = WorkflowService(
        live_service=live_service,
        query_service=query_service,
        decode_service=decode_service,
        replay_service=replay_service,
    )

    started = await live_service.start(reset_session=False, start_recording_if_stopped=False)
    result = await workflow_service.analyze_live_signature_flow(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        path_keywords=["secure", "submit"],
        signature_hints=["sign", "ts"],
        limit=20,
        advance=True,
        decode_bodies=True,
        run_replay=False,
    )

    assert result["analysis_status"] == "ok"
    assert result["report"]["selected_request"]["path"] == "/api/secure/submit"
    assert result["summary"]["signature_candidate_fields"]
    assert "signature-sensitive" in result["report"]["overview"]
    assert result["report"]["signature_analysis"]["candidate_count"] >= 1
    assert result["summary"]["mutation_plan_overview"]["candidate_target_count"] >= 1
    top_target = result["evidence"]["mutation_plan"]["targets"][0]
    assert "sign" in top_target["field"] or "ts" in top_target["field"]
    for variant in result["evidence"]["mutation_plan"]["variants"]:
        assert set(variant["replay_recipe"].keys()).issubset(
            {"query_overrides", "json_overrides", "form_overrides", "header_overrides", "body_text_override"}
        )

