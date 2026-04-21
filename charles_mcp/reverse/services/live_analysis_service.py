"""Near-real-time snapshot analysis built on official Charles exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import time
from uuid import uuid4

from defusedxml import ElementTree as ET

from charles_mcp.reverse.models import CaptureSourceFormat, CaptureSourceKind
from charles_mcp.reverse.services.charles_control_service import CharlesControlService
from charles_mcp.reverse.services.ingest_service import IngestService
from charles_mcp.reverse.services.query_service import QueryService


@dataclass
class LiveSessionState:
    live_session_id: str
    created_at: str
    last_access_monotonic: float
    initial_recording: bool
    managed_recording: bool
    baseline_transaction_count: int
    cursor_transaction_count: int
    latest_capture_id: str | None = None
    snapshot_capture_ids: list[str] = field(default_factory=list)


class LiveAnalysisService:
    """Manage live snapshot sessions without relying on undocumented JSON export."""

    def __init__(
        self,
        *,
        control_service: CharlesControlService,
        ingest_service: IngestService,
        query_service: QueryService,
        temp_dir: Path,
        session_ttl_seconds: int = 900,
        snapshot_history_limit: int = 20,
    ) -> None:
        self.control_service = control_service
        self.ingest_service = ingest_service
        self.query_service = query_service
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.session_ttl_seconds = max(session_ttl_seconds, 1)
        self.snapshot_history_limit = max(snapshot_history_limit, 1)
        self._sessions: dict[str, LiveSessionState] = {}

    async def start(
        self,
        *,
        reset_session: bool = False,
        start_recording_if_stopped: bool = True,
        snapshot_format: CaptureSourceFormat = CaptureSourceFormat.XML,
    ) -> dict:
        self._prune_expired_sessions()
        status = await self.control_service.get_recording_status()
        initial_recording = bool(status["is_recording"])
        managed_recording = False

        if reset_session:
            await self.control_service.clear_session()

        if start_recording_if_stopped and not initial_recording:
            await self.control_service.start_recording()
            managed_recording = True

        baseline_count = await self._current_transaction_count()
        live_session_id = f"live-{uuid4().hex}"
        self._sessions[live_session_id] = LiveSessionState(
            live_session_id=live_session_id,
            created_at=datetime.now().isoformat(),
            last_access_monotonic=time.monotonic(),
            initial_recording=initial_recording,
            managed_recording=managed_recording,
            baseline_transaction_count=baseline_count,
            cursor_transaction_count=baseline_count,
        )
        return {
            "live_session_id": live_session_id,
            "initial_recording": initial_recording,
            "managed_recording": managed_recording,
            "baseline_transaction_count": baseline_count,
            "reset_session": reset_session,
            "snapshot_format": snapshot_format.value,
        }

    async def read(
        self,
        *,
        live_session_id: str,
        snapshot_format: CaptureSourceFormat = CaptureSourceFormat.XML,
        host_contains: str | None = None,
        path_contains: str | None = None,
        method_in: list[str] | None = None,
        status_in: list[int] | None = None,
        limit: int = 20,
        advance: bool = True,
    ) -> dict:
        self._prune_expired_sessions()
        state = self._require(live_session_id)
        state.last_access_monotonic = time.monotonic()
        imported = await self._snapshot_current_session(snapshot_format=snapshot_format)
        state.latest_capture_id = imported["capture_id"]
        state.snapshot_capture_ids.append(imported["capture_id"])
        if len(state.snapshot_capture_ids) > self.snapshot_history_limit:
            state.snapshot_capture_ids = state.snapshot_capture_ids[-self.snapshot_history_limit :]

        current_transaction_count = self.query_service.store.count_entries(
            capture_id=imported["capture_id"],
            exclude_host="control.charles",
        )
        all_entries = self.query_service.store.list_entries(
            capture_id=imported["capture_id"],
            limit=max(imported["entry_count"], current_transaction_count, 1),
            offset=0,
        )
        non_control_entries = [entry for entry in all_entries if entry.host != "control.charles"]
        unseen_entries = non_control_entries[state.cursor_transaction_count :]
        filtered_entries = [
            entry for entry in unseen_entries if _entry_matches(
                entry,
                host_contains=host_contains,
                path_contains=path_contains,
                method_in=method_in,
                status_in=status_in,
            )
        ]
        new_transaction_count = max(current_transaction_count - state.cursor_transaction_count, 0)
        if advance:
            state.cursor_transaction_count = current_transaction_count

        return {
            "live_session_id": live_session_id,
            "capture_id": imported["capture_id"],
            "snapshot_format": snapshot_format.value,
            "current_transaction_count": current_transaction_count,
            "new_transaction_count": new_transaction_count,
            "cursor_transaction_count": state.cursor_transaction_count,
            "items": [
                self.query_service.entry_summary(entry)
                for entry in filtered_entries[:limit]
            ],
            "returned": min(len(filtered_entries), limit),
        }

    async def stop(self, *, live_session_id: str, restore_recording: bool = True) -> dict:
        self._prune_expired_sessions()
        state = self._require(live_session_id)
        restored = False
        if restore_recording and state.managed_recording and not state.initial_recording:
            await self.control_service.stop_recording()
            restored = True
        del self._sessions[live_session_id]
        return {
            "live_session_id": live_session_id,
            "restored_recording": restored,
            "initial_recording": state.initial_recording,
            "managed_recording": state.managed_recording,
            "latest_capture_id": state.latest_capture_id,
            "snapshot_capture_ids": state.snapshot_capture_ids,
        }

    async def status(self, live_session_id: str | None = None) -> dict:
        self._prune_expired_sessions()
        charles_status = await self.control_service.get_recording_status()
        if live_session_id is None:
            return {
                "charles_recording": charles_status,
                "active_live_sessions": list(self._sessions.keys()),
            }
        state = self._require(live_session_id)
        return {
            "charles_recording": charles_status,
            "live_session": {
                "live_session_id": state.live_session_id,
                "created_at": state.created_at,
                "initial_recording": state.initial_recording,
                "managed_recording": state.managed_recording,
                "baseline_transaction_count": state.baseline_transaction_count,
                "cursor_transaction_count": state.cursor_transaction_count,
                "latest_capture_id": state.latest_capture_id,
                "snapshot_capture_ids": state.snapshot_capture_ids,
            },
        }

    def _require(self, live_session_id: str) -> LiveSessionState:
        if live_session_id not in self._sessions:
            raise ValueError(f"live_session_id `{live_session_id}` was not found")
        return self._sessions[live_session_id]

    def _prune_expired_sessions(self) -> None:
        now = time.monotonic()
        expired_ids = [
            live_session_id
            for live_session_id, state in self._sessions.items()
            if now - state.last_access_monotonic > self.session_ttl_seconds
        ]
        for live_session_id in expired_ids:
            del self._sessions[live_session_id]

    async def _current_transaction_count(self) -> int:
        xml = await self.control_service.export_session_xml()
        return _count_non_control_transactions(xml)

    async def _snapshot_current_session(self, *, snapshot_format: CaptureSourceFormat) -> dict:
        if snapshot_format == CaptureSourceFormat.XML:
            path = self.temp_dir / f"{uuid4().hex}.xml"
            path.write_text(await self.control_service.export_session_xml(), encoding="utf-8")
        elif snapshot_format == CaptureSourceFormat.NATIVE:
            path = self.temp_dir / f"{uuid4().hex}.chls"
            path.write_bytes(await self.control_service.download_session_native())
        else:
            raise ValueError("live snapshot supports only xml or native")

        return self.ingest_service.import_session(
            path=str(path),
            source_format=snapshot_format,
            source_kind=CaptureSourceKind.LIVE_SNAPSHOT,
        )


def _count_non_control_transactions(xml: str) -> int:
    root = ET.fromstring(xml)
    count = 0
    for txn in root.findall("transaction"):
        if (txn.attrib.get("host") or "") == "control.charles":
            continue
        count += 1
    return count


def _entry_matches(
    entry,
    *,
    host_contains: str | None,
    path_contains: str | None,
    method_in: list[str] | None,
    status_in: list[int] | None,
) -> bool:
    if host_contains and host_contains.lower() not in (entry.host or "").lower():
        return False
    if path_contains and path_contains.lower() not in (entry.path or "").lower():
        return False
    if method_in and (entry.method or "").upper() not in {item.upper() for item in method_in}:
        return False
    if status_in and entry.status_code not in set(status_in):
        return False
    return True

