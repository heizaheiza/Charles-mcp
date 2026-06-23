import re

import pytest

from charles_mcp.config import Config
from charles_mcp.live_state import LiveCaptureManager
from charles_mcp.schemas.traffic_query import TrafficQuery
from charles_mcp.services.history_capture import RecordingHistoryService
from charles_mcp.services.traffic_analysis import TrafficAnalysisService
from charles_mcp.services.traffic_normalizer import TrafficNormalizer
from charles_mcp.services.traffic_query_service import TrafficQueryService


def _entry(path: str = "/api/login") -> dict:
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
            "header": {
                "firstLine": f"POST {path} HTTP/1.1",
                "headers": [{"name": "Authorization", "value": "Bearer live-secret"}],
            },
            "sizes": {"body": 64},
            "body": {"text": '{"password":"super-secret","payload":"abcdef"}'},
        },
        "response": {
            "status": 200,
            "mimeType": "application/json",
            "header": {"firstLine": "HTTP/1.1 200 OK", "headers": []},
            "sizes": {"body": 80},
            "body": {"text": '{"ok":true,"access_token":"token-value"}'},
        },
    }


def test_live_fingerprint_components_exclude_body_payload() -> None:
    manager = LiveCaptureManager()

    components = manager._fingerprint_components(_entry())

    assert "super-secret" not in components
    assert "token-value" not in components
    assert "/api/login" in components


def test_history_keyword_regex_compiles_once(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RecordingHistoryService(Config())
    compile_calls: list[str] = []
    real_compile = re.compile

    def _counted_compile(pattern: str, flags: int = 0):
        compile_calls.append(pattern)
        return real_compile(pattern, flags)

    monkeypatch.setattr("charles_mcp.services.history_capture.re.compile", _counted_compile)

    result = service.filter_entries(
        [_entry("/api/login"), _entry("/api/profile")],
        keyword_regex="token|profile",
    )

    assert len(result) == 2
    assert compile_calls == ["token|profile"]


class _FakeLiveService:
    async def read(self, *args, **kwargs):
        raise AssertionError("live path should not be used in this test")


class _FakeHistoryService:
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    async def load_latest_with_path(self) -> tuple[str, list[dict]]:
        return ("package/perf.chlsj", list(self.items))

    async def get_snapshot(self, recording_path: str) -> list[dict]:
        return list(self.items)

    async def load_latest(self) -> list[dict]:
        return list(self.items)


@pytest.mark.asyncio
async def test_query_service_classifies_each_entry_once(monkeypatch: pytest.MonkeyPatch) -> None:
    query_classify_calls = 0
    normalizer_classify_calls = 0

    from charles_mcp.analyzers.resource_classifier import classify_entry as real_classify

    def _query_classify(entry: dict):
        nonlocal query_classify_calls
        query_classify_calls += 1
        return real_classify(entry)

    def _normalizer_classify(entry: dict):
        nonlocal normalizer_classify_calls
        normalizer_classify_calls += 1
        return real_classify(entry)

    monkeypatch.setattr("charles_mcp.services.traffic_query_orchestrator.classify_entry", _query_classify)
    monkeypatch.setattr("charles_mcp.services.traffic_normalizer.classify_entry", _normalizer_classify)

    service = TrafficQueryService(
        live_service=_FakeLiveService(),
        history_service=_FakeHistoryService([_entry()]),
        normalizer=TrafficNormalizer(Config()),
        analysis_service=TrafficAnalysisService(),
    )

    await service.analyze_recorded_traffic(
        recording_path=None,
        query=TrafficQuery(),
    )

    assert query_classify_calls == 1
    assert normalizer_classify_calls == 0


@pytest.mark.asyncio
async def test_normalize_diff_cache_reuses_unchanged_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated polls over the same raw entries should hit the diff cache.

    On the second pass classify_entry must never be called and normalize_entry
    must be skipped because both results are reused from the cache. This
    locks in the optimization that lets agents poll query_live_capture_entries
    repeatedly without re-doing CPU work for unchanged traffic.
    """
    from charles_mcp.analyzers.resource_classifier import classify_entry as real_classify

    classify_calls = 0

    def _counting_classify(entry: dict):
        nonlocal classify_calls
        classify_calls += 1
        return real_classify(entry)

    monkeypatch.setattr(
        "charles_mcp.services.traffic_query_orchestrator.classify_entry",
        _counting_classify,
    )

    entries = [_entry("/api/login"), _entry("/api/profile"), _entry("/api/wallet")]
    service = TrafficQueryService(
        live_service=_FakeLiveService(),
        history_service=_FakeHistoryService(entries),
        normalizer=TrafficNormalizer(Config()),
        analysis_service=TrafficAnalysisService(),
    )

    # Warm-up: every entry should be classified + normalized exactly once.
    await service.analyze_recorded_traffic(recording_path=None, query=TrafficQuery())
    assert classify_calls == len(entries)
    stats_after_warmup = dict(service.orchestrator.normalize_cache_stats)
    assert stats_after_warmup["misses"] == len(entries)
    assert stats_after_warmup["hits"] == 0

    # Reset call counters and replay the exact same query.
    classify_calls = 0
    normalize_calls = 0
    real_normalize = service.orchestrator.normalizer.normalize_entry

    def _counting_normalize(*args, **kwargs):
        nonlocal normalize_calls
        normalize_calls += 1
        return real_normalize(*args, **kwargs)

    monkeypatch.setattr(
        service.orchestrator.normalizer,
        "normalize_entry",
        _counting_normalize,
    )

    await service.analyze_recorded_traffic(recording_path=None, query=TrafficQuery())

    # Every entry should now be served from cache.
    assert classify_calls == 0
    assert normalize_calls == 0
    final_stats = service.orchestrator.normalize_cache_stats
    assert final_stats["hits"] == len(entries)
    assert final_stats["misses"] == stats_after_warmup["misses"]


@pytest.mark.asyncio
async def test_normalize_diff_cache_evicts_disappeared_entries() -> None:
    """If a raw entry vanishes between calls, its cached value must be dropped.

    Otherwise the cache would grow unbounded across a long live session.
    """
    initial = [_entry("/api/login"), _entry("/api/profile")]
    reduced = [_entry("/api/login")]
    history_service = _FakeHistoryService(initial)
    service = TrafficQueryService(
        live_service=_FakeLiveService(),
        history_service=history_service,
        normalizer=TrafficNormalizer(Config()),
        analysis_service=TrafficAnalysisService(),
    )

    await service.analyze_recorded_traffic(recording_path=None, query=TrafficQuery())
    scope_caches = list(service.orchestrator._normalize_cache.values())
    assert len(scope_caches) == 1
    assert len(scope_caches[0]) == len(initial)

    history_service.items = list(reduced)
    await service.analyze_recorded_traffic(recording_path=None, query=TrafficQuery())

    scope_caches_after = list(service.orchestrator._normalize_cache.values())
    assert len(scope_caches_after) == 1
    assert len(scope_caches_after[0]) == len(reduced)
