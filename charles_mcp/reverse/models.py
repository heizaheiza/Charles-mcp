"""Canonical models for the vnext reverse-analysis data plane."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CaptureSourceKind(str, Enum):
    LIVE_SNAPSHOT = "live_snapshot"
    HISTORY_IMPORT = "history_import"


class CaptureSourceFormat(str, Enum):
    XML = "xml"
    NATIVE = "native"
    LEGACY_JSON = "legacy_json"


class BodyStorageKind(str, Enum):
    INLINE = "inline"
    EXTERNAL_FILE = "external_file"


class BodyPreservationLevel(str, Enum):
    RAW = "raw"
    TEXT_ONLY = "text_only"
    MISSING = "missing"


class ArtifactType(str, Enum):
    JSON = "json"
    FORM = "form"
    MULTIPART = "multipart"
    PROTOBUF = "protobuf"
    GZIP_TEXT = "gzip_text"
    BR_TEXT = "br_text"
    ZSTD_TEXT = "zstd_text"
    OPAQUE_BINARY = "opaque_binary"
    PLAIN_TEXT = "plain_text"


class ExperimentType(str, Enum):
    REPLAY = "replay"
    MUTATE = "mutate"
    DIFF = "diff"


class TargetSurface(str, Enum):
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    JSON_PATH = "json_path"
    FORM_FIELD = "form_field"
    PROTOBUF_FIELD = "protobuf_field"
    RAW_BODY = "raw_body"


class RunExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class FindingSubjectType(str, Enum):
    CAPTURE = "capture"
    ENTRY = "entry"
    RUN = "run"


class FindingType(str, Enum):
    SIGNATURE_CANDIDATE = "signature_candidate"
    STABLE_PARAM = "stable_param"
    NOISE_PARAM = "noise_param"
    DECODE_GAP = "decode_gap"
    REPLAY_FAILURE = "replay_failure"
    AUTH_DEPENDENCY = "auth_dependency"


class Capture(BaseModel):
    capture_id: str
    source_kind: CaptureSourceKind
    source_format: CaptureSourceFormat
    charles_origin: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    snapshot_seq: int | None = None
    ingest_status: str = "pending"
    entry_count: int = 0
    parent_case_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Entry(BaseModel):
    entry_id: str
    capture_id: str
    sequence_no: int
    method: str
    scheme: str | None = None
    host: str
    path: str
    query: str | None = None
    status_code: int | None = None
    timing_summary: dict[str, Any] = Field(default_factory=dict)
    size_summary: dict[str, Any] = Field(default_factory=dict)
    redirect_from_entry_id: str | None = None
    auth_context_id: str | None = None
    fingerprint: str | None = None
    replayability_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Request(BaseModel):
    request_id: str
    entry_id: str
    first_line: str | None = None
    http_version: str | None = None
    headers: dict[str, list[str]] = Field(default_factory=dict)
    cookies: dict[str, Any] = Field(default_factory=dict)
    content_type: str | None = None
    content_encoding: str | None = None
    body_blob_id: str | None = None
    raw_header_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Response(BaseModel):
    response_id: str
    entry_id: str
    status_code: int | None = None
    reason_phrase: str | None = None
    headers: dict[str, list[str]] = Field(default_factory=dict)
    set_cookies: dict[str, Any] = Field(default_factory=dict)
    content_type: str | None = None
    content_encoding: str | None = None
    body_blob_id: str | None = None
    redirect_location: str | None = None
    raw_header_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BodyBlob(BaseModel):
    body_blob_id: str
    storage_kind: BodyStorageKind
    byte_length: int | None = None
    text_length: int | None = None
    sha256: str | None = None
    is_binary: bool = False
    charset: str | None = None
    raw_bytes: bytes | None = Field(default=None, exclude=True)
    raw_text: str | None = None
    external_ref: str | None = None
    preservation_level: BodyPreservationLevel = BodyPreservationLevel.RAW
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecodedArtifact(BaseModel):
    artifact_id: str
    body_blob_id: str
    artifact_type: ArtifactType
    decoder_name: str
    decoder_version: str | None = None
    descriptor_ref: str | None = None
    preview_text: str | None = None
    structured_json: dict[str, Any] | list[Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Experiment(BaseModel):
    experiment_id: str
    baseline_entry_id: str
    experiment_type: ExperimentType
    target_surface: TargetSurface
    mutation_strategy: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    status: str = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Run(BaseModel):
    run_id: str
    experiment_id: str
    variant_label: str
    request_snapshot: dict[str, Any] = Field(default_factory=dict)
    execution_status: RunExecutionStatus
    response_status: int | None = None
    latency_ms: int | None = None
    response_body_blob_id: str | None = None
    diff_summary: dict[str, Any] = Field(default_factory=dict)
    error_class: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    finding_id: str
    subject_type: FindingSubjectType
    subject_id: str
    finding_type: FindingType
    severity: str
    confidence: float
    title: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendation: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
