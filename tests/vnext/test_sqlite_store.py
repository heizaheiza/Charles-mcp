from datetime import datetime

from charles_mcp.reverse.models import (
    ArtifactType,
    BodyBlob,
    BodyPreservationLevel,
    BodyStorageKind,
    Capture,
    CaptureSourceFormat,
    CaptureSourceKind,
    DecodedArtifact,
    Entry,
    Experiment,
    ExperimentType,
    Finding,
    FindingSubjectType,
    FindingType,
    Request,
    Response,
    Run,
    RunExecutionStatus,
    TargetSurface,
)
from charles_mcp.reverse.storage import SQLiteStore


def test_sqlite_store_round_trips_entry_graph_and_findings(tmp_path):
    store = SQLiteStore(tmp_path / "reverse-vnext.sqlite3")

    capture = Capture(
        capture_id="cap-1",
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
        source_format=CaptureSourceFormat.XML,
        started_at=datetime(2026, 4, 13, 12, 0, 0),
        entry_count=1,
    )
    request_body = BodyBlob(
        body_blob_id="blob-req",
        storage_kind=BodyStorageKind.INLINE,
        preservation_level=BodyPreservationLevel.RAW,
        raw_text='{"user":"alice"}',
        byte_length=16,
        text_length=16,
    )
    response_body = BodyBlob(
        body_blob_id="blob-resp",
        storage_kind=BodyStorageKind.INLINE,
        preservation_level=BodyPreservationLevel.RAW,
        raw_text='{"token":"abc"}',
        byte_length=15,
        text_length=15,
    )
    entry = Entry(
        entry_id="entry-1",
        capture_id="cap-1",
        sequence_no=1,
        method="POST",
        scheme="https",
        host="api.example.com",
        path="/v1/login",
        status_code=200,
        timing_summary={"total_ms": 120},
        size_summary={"response_bytes": 42},
        replayability_score=0.85,
    )
    request = Request(
        request_id="req-1",
        entry_id="entry-1",
        content_type="application/json",
        body_blob_id="blob-req",
        headers={"content-type": ["application/json"]},
    )
    response = Response(
        response_id="resp-1",
        entry_id="entry-1",
        status_code=200,
        content_type="application/json",
        body_blob_id="blob-resp",
        headers={"content-type": ["application/json"]},
    )
    artifact = DecodedArtifact(
        artifact_id="artifact-1",
        body_blob_id="blob-resp",
        artifact_type=ArtifactType.JSON,
        decoder_name="json",
        preview_text='{"token":"abc"}',
        structured_json={"token": "abc"},
    )
    experiment = Experiment(
        experiment_id="exp-1",
        baseline_entry_id="entry-1",
        experiment_type=ExperimentType.MUTATE,
        target_surface=TargetSurface.QUERY,
        created_at=datetime(2026, 4, 13, 12, 1, 0),
    )
    run = Run(
        run_id="run-1",
        experiment_id="exp-1",
        variant_label="drop-ts",
        execution_status=RunExecutionStatus.SUCCEEDED,
        response_status=401,
        diff_summary={"status_changed": True},
        started_at=datetime(2026, 4, 13, 12, 1, 5),
        ended_at=datetime(2026, 4, 13, 12, 1, 6),
    )
    finding = Finding(
        finding_id="finding-1",
        subject_type=FindingSubjectType.RUN,
        subject_id="run-1",
        finding_type=FindingType.SIGNATURE_CANDIDATE,
        severity="high",
        confidence=0.92,
        title="Dropped ts field invalidates the request",
        evidence={"variant": "drop-ts", "status": 401},
        created_at=datetime(2026, 4, 13, 12, 1, 7),
    )

    store.upsert_capture(capture)
    store.upsert_body_blob(request_body)
    store.upsert_body_blob(response_body)
    store.upsert_entry(entry, request, response)
    store.upsert_decoded_artifact(artifact)
    store.upsert_experiment(experiment)
    store.upsert_run(run)
    store.upsert_finding(finding)

    restored_capture = store.get_capture("cap-1")
    snapshot = store.get_entry_snapshot("entry-1")
    findings = store.list_findings(subject_type=FindingSubjectType.RUN, subject_id="run-1")

    assert restored_capture is not None
    assert restored_capture.source_format is CaptureSourceFormat.XML
    assert snapshot is not None
    assert snapshot["entry"].replayability_score == 0.85
    assert snapshot["request"].body_blob_id == "blob-req"
    assert snapshot["response"].body_blob_id == "blob-resp"
    assert snapshot["response_body_blob"].raw_text == '{"token":"abc"}'
    assert len(snapshot["decoded_artifacts"]) == 1
    assert snapshot["decoded_artifacts"][0].artifact_type is ArtifactType.JSON
    assert len(findings) == 1
    assert findings[0].finding_type is FindingType.SIGNATURE_CANDIDATE

