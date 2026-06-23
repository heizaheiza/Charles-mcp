"""Performance-oriented tests for SQLiteStore: WAL pragma and index coverage."""

from __future__ import annotations

from datetime import datetime

from charles_mcp.reverse.models import (
    Capture,
    CaptureSourceFormat,
    CaptureSourceKind,
    Entry,
    Request,
    Response,
)
from charles_mcp.reverse.storage import SQLiteStore


def _seed_store(store: SQLiteStore) -> None:
    """Insert one capture + a handful of entries so the planner has stats."""
    capture = Capture(
        capture_id="cap-perf",
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
        source_format=CaptureSourceFormat.XML,
        started_at=datetime(2026, 4, 14, 12, 0, 0),
        entry_count=4,
    )
    store.upsert_capture(capture)
    for seq, (method, host, path, status) in enumerate(
        [
            ("GET", "api.example.com", "/v1/login", 200),
            ("POST", "api.example.com", "/v1/login", 401),
            ("GET", "static.example.com", "/assets/app.js", 200),
            ("POST", "api.example.com", "/v1/profile", 500),
        ],
        start=1,
    ):
        entry_id = f"entry-perf-{seq}"
        entry = Entry(
            entry_id=entry_id,
            capture_id="cap-perf",
            sequence_no=seq,
            method=method,
            scheme="https",
            host=host,
            path=path,
            status_code=status,
            timing_summary={"total_ms": 10},
            size_summary={"response_bytes": 100},
        )
        request = Request(
            request_id=f"req-perf-{seq}",
            entry_id=entry_id,
            headers={},
        )
        response = Response(
            response_id=f"resp-perf-{seq}",
            entry_id=entry_id,
            status_code=status,
            headers={},
        )
        store.upsert_entry(entry, request, response)


def test_sqlite_store_enables_wal_journal_mode(tmp_path):
    store = SQLiteStore(tmp_path / "reverse-perf.sqlite3")

    with store._connect() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]

    # journal_mode returns the chosen mode as a string (e.g. "wal", "delete").
    assert journal_mode.lower() == "wal"
    # synchronous=NORMAL maps to 1.
    assert synchronous == 1


def test_list_entries_uses_capture_sequence_composite_index(tmp_path):
    store = SQLiteStore(tmp_path / "reverse-perf.sqlite3")
    _seed_store(store)

    with store._connect() as conn:
        plan_rows = conn.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT * FROM entries
            WHERE capture_id = ?
            ORDER BY sequence_no ASC
            LIMIT 20 OFFSET 0
            """,
            ("cap-perf",),
        ).fetchall()

    plan_text = " ".join(row["detail"] for row in plan_rows).lower()
    # The composite (capture_id, sequence_no) index should both filter and
    # satisfy the ORDER BY without an extra sort step.
    assert "idx_entries_capture_sequence" in plan_text
    assert "use temp b-tree" not in plan_text


def test_list_entries_status_filter_uses_capture_status_index(tmp_path):
    store = SQLiteStore(tmp_path / "reverse-perf.sqlite3")
    _seed_store(store)

    with store._connect() as conn:
        plan_rows = conn.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT * FROM entries
            WHERE capture_id = ? AND status_code IN (?, ?)
            ORDER BY sequence_no ASC
            LIMIT 20 OFFSET 0
            """,
            ("cap-perf", 200, 401),
        ).fetchall()

    plan_text = " ".join(row["detail"] for row in plan_rows).lower()
    # Either composite index can serve the predicate; the important guarantee
    # is that SQLite picks an index instead of scanning the table.
    assert (
        "idx_entries_capture_status" in plan_text
        or "idx_entries_capture_sequence" in plan_text
    )
    assert "scan entries" not in plan_text


def test_list_entries_method_filter_uses_upper_method_index(tmp_path):
    store = SQLiteStore(tmp_path / "reverse-perf.sqlite3")
    _seed_store(store)

    with store._connect() as conn:
        plan_rows = conn.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT * FROM entries
            WHERE capture_id = ? AND UPPER(method) IN (?, ?)
            ORDER BY sequence_no ASC
            LIMIT 20 OFFSET 0
            """,
            ("cap-perf", "GET", "POST"),
        ).fetchall()

    plan_text = " ".join(row["detail"] for row in plan_rows).lower()
    assert (
        "idx_entries_capture_method_upper" in plan_text
        or "idx_entries_capture_sequence" in plan_text
    )
    assert "scan entries" not in plan_text
