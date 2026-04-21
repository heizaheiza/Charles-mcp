"""Runtime state management for live Charles capture polling."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha1
from typing import Any, Literal
from uuid import uuid4

from charles_mcp.schemas.live_capture import LiveCaptureReadResult


class LiveCaptureError(Exception):
    """Base error for live capture state problems."""


class LiveCaptureConflictError(LiveCaptureError):
    """Raised when a new capture starts while another is still active."""


class LiveCaptureNotFoundError(LiveCaptureError):
    """Raised when a capture id does not exist."""


@dataclass
class LiveCaptureState:
    """Mutable runtime state for an active or stopped live capture."""

    capture_id: str
    managed: bool
    include_existing: bool
    status: Literal["active", "stopped"] = "active"
    cursor: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    seen_keys: set[str] = field(default_factory=set)
    items: list[dict[str, Any]] = field(default_factory=list)
    last_export_count: int = 0
    warnings: list[str] = field(default_factory=list)


class LiveCaptureManager:
    """Track one active live capture and compute incremental diffs."""

    def __init__(self) -> None:
        self.active: LiveCaptureState | None = None

    def start(
        self,
        *,
        managed: bool,
        include_existing: bool,
        baseline_items: list[dict[str, Any]] | None = None,
    ) -> LiveCaptureState:
        if self.active and self.active.status == "active":
            raise LiveCaptureConflictError(
                f"capture `{self.active.capture_id}` is already active"
            )

        capture = LiveCaptureState(
            capture_id=str(uuid4()),
            managed=managed,
            include_existing=include_existing,
        )

        if baseline_items:
            prepared = list(self._iter_unique_entries(baseline_items))
            capture.last_export_count = len(prepared)
            if include_existing:
                for key, entry in prepared:
                    capture.seen_keys.add(key)
                    capture.items.append(deepcopy(entry))
            else:
                capture.seen_keys.update(key for key, _ in prepared)

        self.active = capture
        return capture

    def require(self, capture_id: str) -> LiveCaptureState:
        if not self.active or self.active.capture_id != capture_id:
            raise LiveCaptureNotFoundError(f"live capture `{capture_id}` was not found")
        return self.active

    def close(self, capture_id: str) -> LiveCaptureState:
        capture = self.require(capture_id)
        capture.status = "stopped"
        self.active = None
        return capture

    def read(
        self,
        capture_id: str,
        raw_items: list[dict[str, Any]],
        *,
        cursor: int | None = None,
        limit: int = 50,
        advance: bool = True,
    ) -> LiveCaptureReadResult:
        capture = self.require(capture_id)
        base_cursor = capture.cursor if cursor is None else max(cursor, 0)

        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        prepared = list(self._iter_unique_entries(raw_items))
        warnings: list[str] = []
        status: Literal["active", "reset_detected", "stopped"] = capture.status

        if len(prepared) < capture.last_export_count:
            warnings.append("session_reset_detected")
            status = "reset_detected"

        working_seen = capture.seen_keys if advance else set(capture.seen_keys)
        working_items = capture.items if advance else list(capture.items)

        if status == "reset_detected":
            working_seen.clear()
            working_items.clear()
            base_cursor = 0

        for key, entry in prepared:
            if key in working_seen:
                continue
            working_seen.add(key)
            working_items.append(deepcopy(entry))

        total_new_items = max(len(working_items) - base_cursor, 0)
        items = working_items[base_cursor: base_cursor + limit]
        next_cursor = base_cursor + len(items)
        truncated = total_new_items > limit

        if advance:
            capture.cursor = next_cursor
            capture.last_export_count = len(prepared)
            capture.warnings = warnings
            if capture.status != "stopped":
                capture.status = "active"

        return LiveCaptureReadResult(
            capture_id=capture.capture_id,
            status=status,
            items=items,
            next_cursor=next_cursor,
            total_new_items=total_new_items,
            truncated=truncated,
            warnings=warnings,
        )

    def _iter_unique_entries(
        self,
        raw_items: list[dict[str, Any]],
    ) -> list[tuple[str, dict[str, Any]]]:
        counts: dict[str, int] = {}
        prepared: list[tuple[str, dict[str, Any]]] = []

        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            if entry.get("host") == "control.charles":
                continue

            fingerprint = self._fingerprint(entry)
            counts[fingerprint] = counts.get(fingerprint, 0) + 1
            prepared.append((f"{fingerprint}:{counts[fingerprint]}", entry))

        return prepared

    def _fingerprint(self, entry: dict[str, Any]) -> str:
        payload = self._fingerprint_components(entry)
        return sha1(payload.encode("utf-8")).hexdigest()

    def _fingerprint_components(self, entry: dict[str, Any]) -> str:
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        request_header = request.get("header") or {}
        response_header = response.get("header") or {}
        request_sizes = request.get("sizes") or {}
        response_sizes = response.get("sizes") or {}
        times = entry.get("times") or {}
        durations = entry.get("durations") or {}

        components = [
            str(entry.get("host") or ""),
            str(entry.get("method") or ""),
            str(entry.get("path") or ""),
            str(entry.get("query") or ""),
            str(entry.get("status") or ""),
            str(response.get("status") or ""),
            str(times.get("start") or ""),
            str(times.get("end") or ""),
            str(durations.get("total") or ""),
            str(entry.get("totalSize") or ""),
            str(request.get("mimeType") or ""),
            str(response.get("mimeType") or ""),
            str(request_sizes.get("body") or ""),
            str(response_sizes.get("body") or ""),
            str(request_header.get("firstLine") or ""),
            str(response_header.get("firstLine") or ""),
        ]
        return "|".join(components)
