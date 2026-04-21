"""SQLite persistence for canonical reverse-analysis entities."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from charles_mcp.reverse.models import (
    BodyBlob,
    Capture,
    DecodedArtifact,
    Entry,
    Experiment,
    Finding,
    FindingSubjectType,
    Request,
    Response,
    Run,
)


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load_json(value: str | None) -> Any:
    if not value:
        return {}
    return json.loads(value)


def _dump_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _load_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteStore:
    """A lightweight repository for the canonical vnext entities."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._transaction_depth = 0
        self._conn = self._create_connection()
        self._initialize()

    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            yield self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            outermost = self._transaction_depth == 0
            if outermost:
                self._conn.execute("BEGIN")
            self._transaction_depth += 1
            try:
                yield self._conn
            except Exception:
                if outermost:
                    self._conn.rollback()
                raise
            else:
                if outermost:
                    self._conn.commit()
            finally:
                self._transaction_depth -= 1

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _initialize(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS captures (
                    capture_id TEXT PRIMARY KEY,
                    source_kind TEXT NOT NULL,
                    source_format TEXT NOT NULL,
                    charles_origin TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    snapshot_seq INTEGER,
                    ingest_status TEXT NOT NULL,
                    entry_count INTEGER NOT NULL,
                    parent_case_id TEXT,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entries (
                    entry_id TEXT PRIMARY KEY,
                    capture_id TEXT NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    method TEXT NOT NULL,
                    scheme TEXT,
                    host TEXT NOT NULL,
                    path TEXT NOT NULL,
                    query TEXT,
                    status_code INTEGER,
                    timing_summary_json TEXT NOT NULL,
                    size_summary_json TEXT NOT NULL,
                    redirect_from_entry_id TEXT,
                    auth_context_id TEXT,
                    fingerprint TEXT,
                    replayability_score REAL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (capture_id) REFERENCES captures(capture_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS body_blobs (
                    body_blob_id TEXT PRIMARY KEY,
                    storage_kind TEXT NOT NULL,
                    byte_length INTEGER,
                    text_length INTEGER,
                    sha256 TEXT,
                    is_binary INTEGER NOT NULL,
                    charset TEXT,
                    raw_bytes BLOB,
                    raw_text TEXT,
                    external_ref TEXT,
                    preservation_level TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    entry_id TEXT NOT NULL UNIQUE,
                    first_line TEXT,
                    http_version TEXT,
                    headers_json TEXT NOT NULL,
                    cookies_json TEXT NOT NULL,
                    content_type TEXT,
                    content_encoding TEXT,
                    body_blob_id TEXT,
                    raw_header_hash TEXT,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE,
                    FOREIGN KEY (body_blob_id) REFERENCES body_blobs(body_blob_id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS responses (
                    response_id TEXT PRIMARY KEY,
                    entry_id TEXT NOT NULL UNIQUE,
                    status_code INTEGER,
                    reason_phrase TEXT,
                    headers_json TEXT NOT NULL,
                    set_cookies_json TEXT NOT NULL,
                    content_type TEXT,
                    content_encoding TEXT,
                    body_blob_id TEXT,
                    redirect_location TEXT,
                    raw_header_hash TEXT,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE,
                    FOREIGN KEY (body_blob_id) REFERENCES body_blobs(body_blob_id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS decoded_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    body_blob_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    decoder_name TEXT NOT NULL,
                    decoder_version TEXT,
                    descriptor_ref TEXT,
                    preview_text TEXT,
                    structured_json TEXT,
                    warnings_json TEXT NOT NULL,
                    confidence REAL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (body_blob_id) REFERENCES body_blobs(body_blob_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    baseline_entry_id TEXT NOT NULL,
                    experiment_type TEXT NOT NULL,
                    target_surface TEXT NOT NULL,
                    mutation_strategy_json TEXT NOT NULL,
                    created_at TEXT,
                    status TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (baseline_entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    variant_label TEXT NOT NULL,
                    request_snapshot_json TEXT NOT NULL,
                    execution_status TEXT NOT NULL,
                    response_status INTEGER,
                    latency_ms INTEGER,
                    response_body_blob_id TEXT,
                    diff_summary_json TEXT NOT NULL,
                    error_class TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE,
                    FOREIGN KEY (response_body_blob_id) REFERENCES body_blobs(body_blob_id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    finding_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    title TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    recommendation TEXT,
                    created_at TEXT,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entries_capture_id ON entries(capture_id);
                CREATE INDEX IF NOT EXISTS idx_requests_entry_id ON requests(entry_id);
                CREATE INDEX IF NOT EXISTS idx_responses_entry_id ON responses(entry_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_body_blob_id ON decoded_artifacts(body_blob_id);
                CREATE INDEX IF NOT EXISTS idx_runs_experiment_id ON runs(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_findings_subject ON findings(subject_type, subject_id);
                """
            )

    def upsert_capture(self, capture: Capture) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO captures (
                    capture_id, source_kind, source_format, charles_origin, started_at, ended_at,
                    snapshot_seq, ingest_status, entry_count, parent_case_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capture_id) DO UPDATE SET
                    source_kind=excluded.source_kind,
                    source_format=excluded.source_format,
                    charles_origin=excluded.charles_origin,
                    started_at=excluded.started_at,
                    ended_at=excluded.ended_at,
                    snapshot_seq=excluded.snapshot_seq,
                    ingest_status=excluded.ingest_status,
                    entry_count=excluded.entry_count,
                    parent_case_id=excluded.parent_case_id,
                    metadata_json=excluded.metadata_json
                """,
                (
                    capture.capture_id,
                    capture.source_kind.value,
                    capture.source_format.value,
                    capture.charles_origin,
                    _dump_datetime(capture.started_at),
                    _dump_datetime(capture.ended_at),
                    capture.snapshot_seq,
                    capture.ingest_status,
                    capture.entry_count,
                    capture.parent_case_id,
                    _dump_json(capture.metadata),
                ),
            )

    def upsert_body_blob(self, body_blob: BodyBlob) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO body_blobs (
                    body_blob_id, storage_kind, byte_length, text_length, sha256, is_binary,
                    charset, raw_bytes, raw_text, external_ref, preservation_level, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(body_blob_id) DO UPDATE SET
                    storage_kind=excluded.storage_kind,
                    byte_length=excluded.byte_length,
                    text_length=excluded.text_length,
                    sha256=excluded.sha256,
                    is_binary=excluded.is_binary,
                    charset=excluded.charset,
                    raw_bytes=excluded.raw_bytes,
                    raw_text=excluded.raw_text,
                    external_ref=excluded.external_ref,
                    preservation_level=excluded.preservation_level,
                    metadata_json=excluded.metadata_json
                """,
                (
                    body_blob.body_blob_id,
                    body_blob.storage_kind.value,
                    body_blob.byte_length,
                    body_blob.text_length,
                    body_blob.sha256,
                    int(body_blob.is_binary),
                    body_blob.charset,
                    body_blob.raw_bytes,
                    body_blob.raw_text,
                    body_blob.external_ref,
                    body_blob.preservation_level.value,
                    _dump_json(body_blob.metadata),
                ),
            )

    def upsert_entry(self, entry: Entry, request: Request, response: Response) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO entries (
                    entry_id, capture_id, sequence_no, method, scheme, host, path, query,
                    status_code, timing_summary_json, size_summary_json, redirect_from_entry_id,
                    auth_context_id, fingerprint, replayability_score, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entry_id) DO UPDATE SET
                    capture_id=excluded.capture_id,
                    sequence_no=excluded.sequence_no,
                    method=excluded.method,
                    scheme=excluded.scheme,
                    host=excluded.host,
                    path=excluded.path,
                    query=excluded.query,
                    status_code=excluded.status_code,
                    timing_summary_json=excluded.timing_summary_json,
                    size_summary_json=excluded.size_summary_json,
                    redirect_from_entry_id=excluded.redirect_from_entry_id,
                    auth_context_id=excluded.auth_context_id,
                    fingerprint=excluded.fingerprint,
                    replayability_score=excluded.replayability_score,
                    metadata_json=excluded.metadata_json
                """,
                (
                    entry.entry_id,
                    entry.capture_id,
                    entry.sequence_no,
                    entry.method,
                    entry.scheme,
                    entry.host,
                    entry.path,
                    entry.query,
                    entry.status_code,
                    _dump_json(entry.timing_summary),
                    _dump_json(entry.size_summary),
                    entry.redirect_from_entry_id,
                    entry.auth_context_id,
                    entry.fingerprint,
                    entry.replayability_score,
                    _dump_json(entry.metadata),
                ),
            )
            conn.execute(
                """
                INSERT INTO requests (
                    request_id, entry_id, first_line, http_version, headers_json, cookies_json,
                    content_type, content_encoding, body_blob_id, raw_header_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    entry_id=excluded.entry_id,
                    first_line=excluded.first_line,
                    http_version=excluded.http_version,
                    headers_json=excluded.headers_json,
                    cookies_json=excluded.cookies_json,
                    content_type=excluded.content_type,
                    content_encoding=excluded.content_encoding,
                    body_blob_id=excluded.body_blob_id,
                    raw_header_hash=excluded.raw_header_hash,
                    metadata_json=excluded.metadata_json
                """,
                (
                    request.request_id,
                    request.entry_id,
                    request.first_line,
                    request.http_version,
                    _dump_json(request.headers),
                    _dump_json(request.cookies),
                    request.content_type,
                    request.content_encoding,
                    request.body_blob_id,
                    request.raw_header_hash,
                    _dump_json(request.metadata),
                ),
            )
            conn.execute(
                """
                INSERT INTO responses (
                    response_id, entry_id, status_code, reason_phrase, headers_json,
                    set_cookies_json, content_type, content_encoding, body_blob_id,
                    redirect_location, raw_header_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(response_id) DO UPDATE SET
                    entry_id=excluded.entry_id,
                    status_code=excluded.status_code,
                    reason_phrase=excluded.reason_phrase,
                    headers_json=excluded.headers_json,
                    set_cookies_json=excluded.set_cookies_json,
                    content_type=excluded.content_type,
                    content_encoding=excluded.content_encoding,
                    body_blob_id=excluded.body_blob_id,
                    redirect_location=excluded.redirect_location,
                    raw_header_hash=excluded.raw_header_hash,
                    metadata_json=excluded.metadata_json
                """,
                (
                    response.response_id,
                    response.entry_id,
                    response.status_code,
                    response.reason_phrase,
                    _dump_json(response.headers),
                    _dump_json(response.set_cookies),
                    response.content_type,
                    response.content_encoding,
                    response.body_blob_id,
                    response.redirect_location,
                    response.raw_header_hash,
                    _dump_json(response.metadata),
                ),
            )

    def upsert_decoded_artifact(self, artifact: DecodedArtifact) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO decoded_artifacts (
                    artifact_id, body_blob_id, artifact_type, decoder_name, decoder_version,
                    descriptor_ref, preview_text, structured_json, warnings_json, confidence,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    body_blob_id=excluded.body_blob_id,
                    artifact_type=excluded.artifact_type,
                    decoder_name=excluded.decoder_name,
                    decoder_version=excluded.decoder_version,
                    descriptor_ref=excluded.descriptor_ref,
                    preview_text=excluded.preview_text,
                    structured_json=excluded.structured_json,
                    warnings_json=excluded.warnings_json,
                    confidence=excluded.confidence,
                    metadata_json=excluded.metadata_json
                """,
                (
                    artifact.artifact_id,
                    artifact.body_blob_id,
                    artifact.artifact_type.value,
                    artifact.decoder_name,
                    artifact.decoder_version,
                    artifact.descriptor_ref,
                    artifact.preview_text,
                    _dump_json(artifact.structured_json) if artifact.structured_json is not None else None,
                    _dump_json(artifact.warnings),
                    artifact.confidence,
                    _dump_json(artifact.metadata),
                ),
            )

    def upsert_experiment(self, experiment: Experiment) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO experiments (
                    experiment_id, baseline_entry_id, experiment_type, target_surface,
                    mutation_strategy_json, created_at, status, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(experiment_id) DO UPDATE SET
                    baseline_entry_id=excluded.baseline_entry_id,
                    experiment_type=excluded.experiment_type,
                    target_surface=excluded.target_surface,
                    mutation_strategy_json=excluded.mutation_strategy_json,
                    created_at=excluded.created_at,
                    status=excluded.status,
                    metadata_json=excluded.metadata_json
                """,
                (
                    experiment.experiment_id,
                    experiment.baseline_entry_id,
                    experiment.experiment_type.value,
                    experiment.target_surface.value,
                    _dump_json(experiment.mutation_strategy),
                    _dump_datetime(experiment.created_at),
                    experiment.status,
                    _dump_json(experiment.metadata),
                ),
            )

    def upsert_run(self, run: Run) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, experiment_id, variant_label, request_snapshot_json,
                    execution_status, response_status, latency_ms, response_body_blob_id,
                    diff_summary_json, error_class, started_at, ended_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    experiment_id=excluded.experiment_id,
                    variant_label=excluded.variant_label,
                    request_snapshot_json=excluded.request_snapshot_json,
                    execution_status=excluded.execution_status,
                    response_status=excluded.response_status,
                    latency_ms=excluded.latency_ms,
                    response_body_blob_id=excluded.response_body_blob_id,
                    diff_summary_json=excluded.diff_summary_json,
                    error_class=excluded.error_class,
                    started_at=excluded.started_at,
                    ended_at=excluded.ended_at,
                    metadata_json=excluded.metadata_json
                """,
                (
                    run.run_id,
                    run.experiment_id,
                    run.variant_label,
                    _dump_json(run.request_snapshot),
                    run.execution_status.value,
                    run.response_status,
                    run.latency_ms,
                    run.response_body_blob_id,
                    _dump_json(run.diff_summary),
                    run.error_class,
                    _dump_datetime(run.started_at),
                    _dump_datetime(run.ended_at),
                    _dump_json(run.metadata),
                ),
            )

    def upsert_finding(self, finding: Finding) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO findings (
                    finding_id, subject_type, subject_id, finding_type, severity, confidence,
                    title, evidence_json, recommendation, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(finding_id) DO UPDATE SET
                    subject_type=excluded.subject_type,
                    subject_id=excluded.subject_id,
                    finding_type=excluded.finding_type,
                    severity=excluded.severity,
                    confidence=excluded.confidence,
                    title=excluded.title,
                    evidence_json=excluded.evidence_json,
                    recommendation=excluded.recommendation,
                    created_at=excluded.created_at,
                    metadata_json=excluded.metadata_json
                """,
                (
                    finding.finding_id,
                    finding.subject_type.value,
                    finding.subject_id,
                    finding.finding_type.value,
                    finding.severity,
                    finding.confidence,
                    finding.title,
                    _dump_json(finding.evidence),
                    finding.recommendation,
                    _dump_datetime(finding.created_at),
                    _dump_json(finding.metadata),
                ),
            )

    def get_capture(self, capture_id: str) -> Capture | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM captures WHERE capture_id = ?", (capture_id,)).fetchone()
        if row is None:
            return None
        return Capture(
            capture_id=row["capture_id"],
            source_kind=row["source_kind"],
            source_format=row["source_format"],
            charles_origin=row["charles_origin"],
            started_at=_load_datetime(row["started_at"]),
            ended_at=_load_datetime(row["ended_at"]),
            snapshot_seq=row["snapshot_seq"],
            ingest_status=row["ingest_status"],
            entry_count=row["entry_count"],
            parent_case_id=row["parent_case_id"],
            metadata=_load_json(row["metadata_json"]),
        )

    def list_captures(self, *, limit: int = 20) -> list[Capture]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM captures
                ORDER BY COALESCE(ended_at, started_at) DESC, capture_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            Capture(
                capture_id=row["capture_id"],
                source_kind=row["source_kind"],
                source_format=row["source_format"],
                charles_origin=row["charles_origin"],
                started_at=_load_datetime(row["started_at"]),
                ended_at=_load_datetime(row["ended_at"]),
                snapshot_seq=row["snapshot_seq"],
                ingest_status=row["ingest_status"],
                entry_count=row["entry_count"],
                parent_case_id=row["parent_case_id"],
                metadata=_load_json(row["metadata_json"]),
            )
            for row in rows
        ]

    def list_entries(
        self,
        *,
        capture_id: str,
        host_contains: str | None = None,
        path_contains: str | None = None,
        method_in: list[str] | None = None,
        status_in: list[int] | None = None,
        min_sequence_no: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Entry]:
        clauses = ["capture_id = ?"]
        params: list[Any] = [capture_id]

        if host_contains:
            clauses.append("LOWER(host) LIKE ?")
            params.append(f"%{host_contains.lower()}%")
        if path_contains:
            clauses.append("LOWER(path) LIKE ?")
            params.append(f"%{path_contains.lower()}%")
        if method_in:
            normalized = [item.upper() for item in method_in]
            placeholders = ", ".join("?" for _ in normalized)
            clauses.append(f"UPPER(method) IN ({placeholders})")
            params.extend(normalized)
        if status_in:
            placeholders = ", ".join("?" for _ in status_in)
            clauses.append(f"status_code IN ({placeholders})")
            params.extend(status_in)
        if min_sequence_no is not None:
            clauses.append("sequence_no >= ?")
            params.append(min_sequence_no)

        params.extend([limit, offset])
        query = f"""
            SELECT * FROM entries
            WHERE {' AND '.join(clauses)}
            ORDER BY sequence_no ASC
            LIMIT ? OFFSET ?
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._entry_from_row(row) for row in rows]

    def count_entries(
        self,
        *,
        capture_id: str,
        exclude_host: str | None = None,
    ) -> int:
        clauses = ["capture_id = ?"]
        params: list[Any] = [capture_id]
        if exclude_host is not None:
            clauses.append("host != ?")
            params.append(exclude_host)
        query = f"SELECT COUNT(*) AS total FROM entries WHERE {' AND '.join(clauses)}"
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row["total"]) if row is not None else 0

    def get_entry_snapshot(self, entry_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            entry_row = conn.execute("SELECT * FROM entries WHERE entry_id = ?", (entry_id,)).fetchone()
            if entry_row is None:
                return None
            request_row = conn.execute("SELECT * FROM requests WHERE entry_id = ?", (entry_id,)).fetchone()
            response_row = conn.execute("SELECT * FROM responses WHERE entry_id = ?", (entry_id,)).fetchone()
            body_rows = conn.execute(
                """
                SELECT * FROM body_blobs
                WHERE body_blob_id IN (?, ?)
                """,
                (
                    request_row["body_blob_id"] if request_row else None,
                    response_row["body_blob_id"] if response_row else None,
                ),
            ).fetchall()
            artifact_rows = conn.execute(
                """
                SELECT * FROM decoded_artifacts
                WHERE body_blob_id IN (?, ?)
                ORDER BY artifact_id
                """,
                (
                    request_row["body_blob_id"] if request_row else None,
                    response_row["body_blob_id"] if response_row else None,
                ),
            ).fetchall()

        bodies = {row["body_blob_id"]: self._body_blob_from_row(row) for row in body_rows}
        artifacts = [self._artifact_from_row(row) for row in artifact_rows]
        return {
            "entry": self._entry_from_row(entry_row),
            "request": self._request_from_row(request_row) if request_row else None,
            "response": self._response_from_row(response_row) if response_row else None,
            "request_body_blob": bodies.get(request_row["body_blob_id"]) if request_row else None,
            "response_body_blob": bodies.get(response_row["body_blob_id"]) if response_row else None,
            "decoded_artifacts": artifacts,
        }

    def list_findings(
        self,
        *,
        subject_type: FindingSubjectType | None = None,
        subject_id: str | None = None,
    ) -> list[Finding]:
        query = "SELECT * FROM findings"
        params: list[Any] = []
        clauses: list[str] = []

        if subject_type is not None:
            clauses.append("subject_type = ?")
            params.append(subject_type.value)
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, finding_id"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._finding_from_row(row) for row in rows]

    def list_runs(self, *, experiment_id: str) -> list[Run]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE experiment_id = ? ORDER BY started_at, run_id",
                (experiment_id,),
            ).fetchall()
        return [self._run_from_row(row) for row in rows]

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
        if row is None:
            return None
        return self._experiment_from_row(row)

    def _entry_from_row(self, row: sqlite3.Row) -> Entry:
        return Entry(
            entry_id=row["entry_id"],
            capture_id=row["capture_id"],
            sequence_no=row["sequence_no"],
            method=row["method"],
            scheme=row["scheme"],
            host=row["host"],
            path=row["path"],
            query=row["query"],
            status_code=row["status_code"],
            timing_summary=_load_json(row["timing_summary_json"]),
            size_summary=_load_json(row["size_summary_json"]),
            redirect_from_entry_id=row["redirect_from_entry_id"],
            auth_context_id=row["auth_context_id"],
            fingerprint=row["fingerprint"],
            replayability_score=row["replayability_score"],
            metadata=_load_json(row["metadata_json"]),
        )

    def _request_from_row(self, row: sqlite3.Row) -> Request:
        return Request(
            request_id=row["request_id"],
            entry_id=row["entry_id"],
            first_line=row["first_line"],
            http_version=row["http_version"],
            headers=_load_json(row["headers_json"]),
            cookies=_load_json(row["cookies_json"]),
            content_type=row["content_type"],
            content_encoding=row["content_encoding"],
            body_blob_id=row["body_blob_id"],
            raw_header_hash=row["raw_header_hash"],
            metadata=_load_json(row["metadata_json"]),
        )

    def _response_from_row(self, row: sqlite3.Row) -> Response:
        return Response(
            response_id=row["response_id"],
            entry_id=row["entry_id"],
            status_code=row["status_code"],
            reason_phrase=row["reason_phrase"],
            headers=_load_json(row["headers_json"]),
            set_cookies=_load_json(row["set_cookies_json"]),
            content_type=row["content_type"],
            content_encoding=row["content_encoding"],
            body_blob_id=row["body_blob_id"],
            redirect_location=row["redirect_location"],
            raw_header_hash=row["raw_header_hash"],
            metadata=_load_json(row["metadata_json"]),
        )

    def _body_blob_from_row(self, row: sqlite3.Row) -> BodyBlob:
        return BodyBlob(
            body_blob_id=row["body_blob_id"],
            storage_kind=row["storage_kind"],
            byte_length=row["byte_length"],
            text_length=row["text_length"],
            sha256=row["sha256"],
            is_binary=bool(row["is_binary"]),
            charset=row["charset"],
            raw_bytes=row["raw_bytes"],
            raw_text=row["raw_text"],
            external_ref=row["external_ref"],
            preservation_level=row["preservation_level"],
            metadata=_load_json(row["metadata_json"]),
        )

    def _artifact_from_row(self, row: sqlite3.Row) -> DecodedArtifact:
        return DecodedArtifact(
            artifact_id=row["artifact_id"],
            body_blob_id=row["body_blob_id"],
            artifact_type=row["artifact_type"],
            decoder_name=row["decoder_name"],
            decoder_version=row["decoder_version"],
            descriptor_ref=row["descriptor_ref"],
            preview_text=row["preview_text"],
            structured_json=_load_json(row["structured_json"]) if row["structured_json"] else None,
            warnings=_load_json(row["warnings_json"]),
            confidence=row["confidence"],
            metadata=_load_json(row["metadata_json"]),
        )

    def _finding_from_row(self, row: sqlite3.Row) -> Finding:
        return Finding(
            finding_id=row["finding_id"],
            subject_type=row["subject_type"],
            subject_id=row["subject_id"],
            finding_type=row["finding_type"],
            severity=row["severity"],
            confidence=row["confidence"],
            title=row["title"],
            evidence=_load_json(row["evidence_json"]),
            recommendation=row["recommendation"],
            created_at=_load_datetime(row["created_at"]),
            metadata=_load_json(row["metadata_json"]),
        )

    def _experiment_from_row(self, row: sqlite3.Row) -> Experiment:
        return Experiment(
            experiment_id=row["experiment_id"],
            baseline_entry_id=row["baseline_entry_id"],
            experiment_type=row["experiment_type"],
            target_surface=row["target_surface"],
            mutation_strategy=_load_json(row["mutation_strategy_json"]),
            created_at=_load_datetime(row["created_at"]),
            status=row["status"],
            metadata=_load_json(row["metadata_json"]),
        )

    def _run_from_row(self, row: sqlite3.Row) -> Run:
        return Run(
            run_id=row["run_id"],
            experiment_id=row["experiment_id"],
            variant_label=row["variant_label"],
            request_snapshot=_load_json(row["request_snapshot_json"]),
            execution_status=row["execution_status"],
            response_status=row["response_status"],
            latency_ms=row["latency_ms"],
            response_body_blob_id=row["response_body_blob_id"],
            diff_summary=_load_json(row["diff_summary_json"]),
            error_class=row["error_class"],
            started_at=_load_datetime(row["started_at"]),
            ended_at=_load_datetime(row["ended_at"]),
            metadata=_load_json(row["metadata_json"]),
        )

