from pathlib import Path

import pytest
from defusedxml.common import DefusedXmlException

from charles_mcp.reverse.config import VNextConfig
from charles_mcp.reverse.models import CaptureSourceFormat
from charles_mcp.reverse.services import IngestService, LiveAnalysisService, QueryService
from charles_mcp.reverse.services.live_analysis_service import _count_non_control_transactions
from charles_mcp.reverse.services.charles_control_service import CharlesControlService
from charles_mcp.reverse.storage import SQLiteStore


def _build_snapshot(*paths: str) -> str:
    transactions = []
    for index, path in enumerate(paths, start=1):
        transactions.append(
            f"""
  <transaction method="GET" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="{path}" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-14T12:00:0{index}Z" startTimeMillis="171300000000{index}" responseTime="2026-04-14T12:00:0{index}Z" responseTimeMillis="171300000000{index}" endTime="2026-04-14T12:00:0{index}Z" endTimeMillis="171300000000{index}">
    <request headers="true" body="false">
      <headers><first-line>GET {path} HTTP/1.1</first-line></headers>
    </request>
    <response status="200" headers="true" body="true" mime-type="application/json" charset="utf-8">
      <headers><first-line>HTTP/1.1 200 OK</first-line></headers>
      <body encoding="plain">{{"path":"{path}"}}</body>
    </response>
  </transaction>
"""
        )
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><charles-session>" + "".join(transactions) + "</charles-session>"


def _build_snapshot_with_control(*paths: str) -> str:
    business = _build_snapshot(*paths).replace("</charles-session>", "")
    control = """
  <transaction method="GET" protocolVersion="HTTP/1.1" protocol="http" host="control.charles" port="80" actualPort="80" path="/session/export-xml" query="" remoteAddress="localhost" clientAddress="127.0.0.1" startTime="2026-04-14T12:01:00Z" startTimeMillis="1713000001000" responseTime="2026-04-14T12:01:00Z" responseTimeMillis="1713000001000" endTime="2026-04-14T12:01:00Z" endTimeMillis="1713000001000">
    <request headers="true" body="false">
      <headers><first-line>GET /session/export-xml HTTP/1.1</first-line></headers>
    </request>
    <response status="200" headers="true" body="false" mime-type="text/xml">
      <headers><first-line>HTTP/1.1 200 OK</first-line></headers>
    </response>
  </transaction>
</charles-session>
"""
    return business + control


class _FakeControlService:
    def __init__(self, snapshots: list[str], *, recording: bool = False) -> None:
        self.snapshots = snapshots
        self.recording = recording
        self.index = 0

    async def get_recording_status(self) -> dict:
        return {"is_recording": self.recording, "status_text": "recording" if self.recording else "stopped", "page": ""}

    async def start_recording(self) -> None:
        self.recording = True

    async def stop_recording(self) -> None:
        self.recording = False

    async def clear_session(self) -> None:
        self.snapshots = [_build_snapshot()]
        self.index = 0

    async def export_session_xml(self) -> str:
        idx = min(self.index, len(self.snapshots) - 1)
        value = self.snapshots[idx]
        self.index += 1
        return value

    async def download_session_native(self) -> bytes:
        raise AssertionError("native export is not used in this test")


@pytest.mark.asyncio
async def test_live_analysis_service_peek_and_read_only_return_new_entries(tmp_path: Path):
    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    query_service = QueryService(store)
    control = _FakeControlService(
        [
            _build_snapshot("/baseline"),
            _build_snapshot("/baseline", "/new-1", "/new-2"),
            _build_snapshot("/baseline", "/new-1", "/new-2", "/new-3"),
        ]
    )
    live_service = LiveAnalysisService(
        control_service=control,  # type: ignore[arg-type]
        ingest_service=ingest_service,
        query_service=query_service,
        temp_dir=config.temp_dir,
    )

    started = await live_service.start(reset_session=False, start_recording_if_stopped=True)
    peeked = await live_service.read(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        limit=10,
        advance=False,
    )
    read = await live_service.read(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        limit=10,
        advance=True,
    )
    stopped = await live_service.stop(live_session_id=started["live_session_id"])

    assert started["managed_recording"] is True
    assert peeked["new_transaction_count"] == 2
    assert [item["path"] for item in peeked["items"]] == ["/new-1", "/new-2"]
    assert read["new_transaction_count"] == 3
    assert [item["path"] for item in read["items"]] == ["/new-1", "/new-2", "/new-3"]
    assert stopped["restored_recording"] is True


@pytest.mark.asyncio
async def test_live_analysis_service_excludes_control_charles_from_cursor_counts(tmp_path: Path):
    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    query_service = QueryService(store)
    control = _FakeControlService(
        [
            _build_snapshot_with_control("/baseline"),
            _build_snapshot_with_control("/baseline", "/new-1"),
            _build_snapshot_with_control("/baseline", "/new-1"),
        ],
        recording=True,
    )
    live_service = LiveAnalysisService(
        control_service=control,  # type: ignore[arg-type]
        ingest_service=ingest_service,
        query_service=query_service,
        temp_dir=config.temp_dir,
    )

    started = await live_service.start(reset_session=False, start_recording_if_stopped=False)
    first = await live_service.read(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        limit=10,
        advance=True,
    )
    second = await live_service.read(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        limit=10,
        advance=True,
    )

    assert started["baseline_transaction_count"] == 1
    assert first["new_transaction_count"] == 1
    assert second["new_transaction_count"] == 0


@pytest.mark.asyncio
async def test_live_analysis_service_prunes_expired_sessions(tmp_path: Path, monkeypatch):
    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    query_service = QueryService(store)
    control = _FakeControlService([_build_snapshot("/baseline")], recording=True)
    live_service = LiveAnalysisService(
        control_service=control,  # type: ignore[arg-type]
        ingest_service=ingest_service,
        query_service=query_service,
        temp_dir=config.temp_dir,
        session_ttl_seconds=5,
    )
    ticks = iter([0.0, 0.0, 10.0, 10.1])
    monkeypatch.setattr(
        "charles_mcp.reverse.services.live_analysis_service.time.monotonic",
        lambda: next(ticks, 10.1),
    )

    started = await live_service.start(reset_session=False, start_recording_if_stopped=False)
    status = await live_service.status()

    assert status["active_live_sessions"] == []
    with pytest.raises(ValueError):
        await live_service.status(live_session_id=started["live_session_id"])


@pytest.mark.asyncio
async def test_live_analysis_service_caps_snapshot_history(tmp_path: Path):
    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    query_service = QueryService(store)
    control = _FakeControlService(
        [
            _build_snapshot("/baseline"),
            _build_snapshot("/baseline", "/new-1"),
            _build_snapshot("/baseline", "/new-1", "/new-2"),
            _build_snapshot("/baseline", "/new-1", "/new-2", "/new-3"),
        ],
        recording=True,
    )
    live_service = LiveAnalysisService(
        control_service=control,  # type: ignore[arg-type]
        ingest_service=ingest_service,
        query_service=query_service,
        temp_dir=config.temp_dir,
        snapshot_history_limit=2,
    )

    started = await live_service.start(reset_session=False, start_recording_if_stopped=False)
    await live_service.read(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        limit=10,
        advance=True,
    )
    await live_service.read(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        limit=10,
        advance=True,
    )
    await live_service.read(
        live_session_id=started["live_session_id"],
        snapshot_format=CaptureSourceFormat.XML,
        limit=10,
        advance=True,
    )
    stopped = await live_service.stop(live_session_id=started["live_session_id"])

    assert len(stopped["snapshot_capture_ids"]) == 2
    assert stopped["latest_capture_id"] == stopped["snapshot_capture_ids"][-1]


def test_count_non_control_transactions_rejects_dtd_entities():
    malicious_xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE charles-session [
  <!ENTITY boom "boom">
]>
<charles-session>
  <transaction host="api.example.com" path="/ping">&boom;</transaction>
</charles-session>
"""

    with pytest.raises(DefusedXmlException):
        _count_non_control_transactions(malicious_xml)

