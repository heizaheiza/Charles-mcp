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


def test_models_accept_enum_strings():
    capture = Capture(
        capture_id="cap-1",
        source_kind="history_import",
        source_format="xml",
        started_at=datetime(2026, 4, 13, 12, 0, 0),
    )

    body = BodyBlob(
        body_blob_id="blob-1",
        storage_kind="inline",
        preservation_level="raw",
        raw_text='{"ok":true}',
    )

    artifact = DecodedArtifact(
        artifact_id="art-1",
        body_blob_id="blob-1",
        artifact_type="json",
        decoder_name="json-decoder",
        structured_json={"ok": True},
    )

    experiment = Experiment(
        experiment_id="exp-1",
        baseline_entry_id="entry-1",
        experiment_type="mutate",
        target_surface="query",
    )

    run = Run(
        run_id="run-1",
        experiment_id="exp-1",
        variant_label="drop-signature",
        execution_status="failed",
    )

    finding = Finding(
        finding_id="finding-1",
        subject_type="run",
        subject_id="run-1",
        finding_type="replay_failure",
        severity="high",
        confidence=0.9,
        title="Signature replay failed",
    )

    assert capture.source_kind is CaptureSourceKind.HISTORY_IMPORT
    assert capture.source_format is CaptureSourceFormat.XML
    assert body.storage_kind is BodyStorageKind.INLINE
    assert body.preservation_level is BodyPreservationLevel.RAW
    assert artifact.artifact_type is ArtifactType.JSON
    assert experiment.experiment_type is ExperimentType.MUTATE
    assert experiment.target_surface is TargetSurface.QUERY
    assert run.execution_status is RunExecutionStatus.FAILED
    assert finding.subject_type is FindingSubjectType.RUN
    assert finding.finding_type is FindingType.REPLAY_FAILURE


def test_entry_request_response_models_have_expected_defaults():
    entry = Entry(
        entry_id="entry-1",
        capture_id="cap-1",
        sequence_no=1,
        method="POST",
        host="api.example.com",
        path="/v1/login",
    )
    request = Request(request_id="req-1", entry_id="entry-1")
    response = Response(response_id="resp-1", entry_id="entry-1")

    assert entry.timing_summary == {}
    assert entry.size_summary == {}
    assert request.headers == {}
    assert response.headers == {}

