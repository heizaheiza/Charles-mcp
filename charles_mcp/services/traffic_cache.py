"""Cache normalized traffic entries by source identity and body mode."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from time import monotonic

from charles_mcp.schemas.traffic import TrafficEntry

SUMMARY_BODY_MODE = "summary"


@dataclass(frozen=True)
class TrafficCacheKey:
    """Cache namespace for one source identity and body mode."""

    source: str
    identity: str
    body_mode: str


@dataclass
class TrafficCacheScope:
    """Stored normalized entries for one cache key."""

    entries: dict[str, TrafficEntry]
    classified_counts: dict[str, int] = field(default_factory=dict)
    created_at: float = field(default_factory=monotonic)


class TrafficEntryCache:
    """Bounded cache for summary/detail traffic entries."""

    def __init__(self, *, max_scopes: int = 32, ttl_seconds: int = 600) -> None:
        self.max_scopes = max_scopes
        self.ttl_seconds = ttl_seconds
        self._scopes: OrderedDict[TrafficCacheKey, TrafficCacheScope] = OrderedDict()
        self._entry_index: dict[tuple[str, str], str] = {}

    def put(
        self,
        *,
        source: str,
        identity: str,
        body_mode: str,
        entries: dict[str, TrafficEntry],
        classified_counts: dict[str, int] | None = None,
    ) -> None:
        self._evict_expired()
        key = TrafficCacheKey(source=source, identity=identity, body_mode=body_mode)
        self._scopes[key] = TrafficCacheScope(
            entries=dict(entries),
            classified_counts=dict(classified_counts or {}),
        )
        self._scopes.move_to_end(key)
        for entry_id in entries:
            self._entry_index[(source, entry_id)] = identity
        self._evict_overflow()

    def get_entry(
        self,
        *,
        source: str,
        identity: str,
        entry_id: str,
        body_mode: str = SUMMARY_BODY_MODE,
    ) -> TrafficEntry | None:
        self._evict_expired()
        key = TrafficCacheKey(source=source, identity=identity, body_mode=body_mode)
        scope = self._scopes.get(key)
        if scope is None:
            return None
        self._scopes.move_to_end(key)
        return scope.entries.get(entry_id)

    def resolve_identity(self, *, source: str, entry_id: str) -> str | None:
        self._evict_expired()
        return self._entry_index.get((source, entry_id))

    def get_classified_counts(self, *, source: str, identity: str) -> dict[str, int]:
        self._evict_expired()
        key = TrafficCacheKey(source=source, identity=identity, body_mode=SUMMARY_BODY_MODE)
        scope = self._scopes.get(key)
        if scope is None:
            return {}
        self._scopes.move_to_end(key)
        return dict(scope.classified_counts)

    def _evict_expired(self) -> None:
        if self.ttl_seconds <= 0:
            return

        now = monotonic()
        expired: list[TrafficCacheKey] = []
        for key, scope in self._scopes.items():
            if now - scope.created_at > self.ttl_seconds:
                expired.append(key)

        for key in expired:
            self._drop_scope(key)

    def _evict_overflow(self) -> None:
        while len(self._scopes) > self.max_scopes:
            oldest_key = next(iter(self._scopes))
            self._drop_scope(oldest_key)

    def _drop_scope(self, key: TrafficCacheKey) -> None:
        scope = self._scopes.pop(key, None)
        if scope is None:
            return
        for entry_id in scope.entries:
            entry_key = (key.source, entry_id)
            if self._entry_index.get(entry_key) == key.identity:
                self._entry_index.pop(entry_key, None)
