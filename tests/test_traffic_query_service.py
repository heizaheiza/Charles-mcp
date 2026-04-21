import pytest

from charles_mcp.config import Config
from charles_mcp.services.traffic_analysis import TrafficAnalysisService
from charles_mcp.services.traffic_normalizer import TrafficNormalizer
from charles_mcp.services.traffic_query_service import TrafficQueryService
from charles_mcp.schemas.traffic_query import TrafficQuery


def _entry(path: str, token: str) -> dict:
    return {
        "status": "COMPLETE",
        "method": "POST",
        "scheme": "https",
        "host": "api.example.com",
        "path": path,
        "query": None,
        "times": {"start": "2026-03-06T10:00:00.000+08:00"},
        "durations": {"total": 18},
        "totalSize": 1200,
        "request": {
            "mimeType": "application/json",
            "header": {
                "firstLine": f"POST {path} HTTP/1.1",
                "headers": [{"name": "Authorization", "value": f"Bearer {token}"}],
            },
            "body": {"text": f'{{"password":"{token}"}}'},
        },
        "response": {
            "status": 200,
            "mimeType": "application/json",
            "header": {
                "firstLine": "HTTP/1.1 200 OK",
                "headers": [{"name": "Set-Cookie", "value": f"sessionid={token}"}],
            },
            "body": {"text": f'{{"access_token":"{token}"}}'},
        },
    }


class _FakeLiveService:
    async def read(self, *args, **kwargs):
        raise AssertionError("live path should not be used in this test")


class _FakeHistoryService:
    def __init__(self) -> None:
        self.snapshots = {
            "package/old.chlsj": [_entry("/old", "old-secret")],
            "package/new.chlsj": [_entry("/new", "new-secret")],
        }
        self.latest_path = "package/old.chlsj"

    async def load_latest_with_path(self) -> tuple[str, list[dict]]:
        return self.latest_path, list(self.snapshots[self.latest_path])

    async def get_snapshot(self, recording_path: str) -> list[dict]:
        return list(self.snapshots[recording_path])

    async def load_latest(self) -> list[dict]:
        return list(self.snapshots[self.latest_path])


def _build_service() -> tuple[TrafficQueryService, _FakeHistoryService]:
    history_service = _FakeHistoryService()
    service = TrafficQueryService(
        live_service=_FakeLiveService(),
        history_service=history_service,
        normalizer=TrafficNormalizer(Config()),
        analysis_service=TrafficAnalysisService(),
    )
    return service, history_service


@pytest.mark.asyncio
async def test_history_detail_remains_bound_to_summary_recording() -> None:
    service, history_service = _build_service()

    summary = await service.analyze_recorded_traffic(
        recording_path=None,
        query=TrafficQuery(include_body_preview=True),
    )
    entry_id = summary.items[0].entry_id

    history_service.latest_path = "package/new.chlsj"
    detail = await service.get_detail(
        source="history",
        entry_id=entry_id,
        include_full_body=True,
    )

    assert detail.detail.entry.recording_path == "package/old.chlsj"
    assert detail.detail.entry.path == "/old"
    assert detail.detail.entry.response.body.full_text == '{"access_token":"old-secret"}'


@pytest.mark.asyncio
async def test_history_detail_requires_recording_identity_when_cache_is_cold() -> None:
    service, _history_service = _build_service()

    with pytest.raises(ValueError, match="recording_path"):
        await service.get_detail(
            source="history",
            entry_id="missing-entry",
            include_full_body=True,
        )
