"""Replay and mutation experiments for imported entries."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import parse_qs, urlencode

import httpx

from charles_mcp.reverse.config import VNextConfig
from charles_mcp.reverse.models import (
    BodyBlob,
    BodyPreservationLevel,
    BodyStorageKind,
    Experiment,
    ExperimentType,
    Finding,
    FindingSubjectType,
    FindingType,
    Run,
    RunExecutionStatus,
    TargetSurface,
)
from charles_mcp.reverse.services.common import (
    apply_query_overrides,
    build_entry_url,
    hash_payload,
    new_identifier,
)
from charles_mcp.reverse.storage import SQLiteStore


class ReplayService:
    """Execute replay and mutation experiments against stored entries."""

    def __init__(self, config: VNextConfig, store: SQLiteStore) -> None:
        self.config = config
        self.store = store

    async def replay_entry(
        self,
        *,
        entry_id: str,
        query_overrides: dict[str, Any] | None = None,
        header_overrides: dict[str, str | None] | None = None,
        json_overrides: dict[str, Any] | None = None,
        form_overrides: dict[str, Any] | None = None,
        body_text_override: str | None = None,
        follow_redirects: bool = True,
        use_proxy: bool = False,
    ) -> dict[str, Any]:
        snapshot = self.store.get_entry_snapshot(entry_id)
        if snapshot is None:
            raise ValueError(f"entry `{entry_id}` was not found")

        entry = snapshot["entry"]
        request = snapshot["request"]
        request_blob = snapshot["request_body_blob"]
        if request is None:
            raise ValueError(f"entry `{entry_id}` is missing request data")

        url = build_entry_url(
            scheme=entry.scheme,
            host=entry.host,
            path=entry.path,
            query=apply_query_overrides(entry.query, query_overrides),
            port=_resolve_entry_port(entry.metadata),
        )
        headers = {name: values[-1] for name, values in request.headers.items()}
        for hop_header in ("host", "content-length", "transfer-encoding"):
            headers.pop(hop_header, None)
        for name, value in (header_overrides or {}).items():
            if value is None:
                headers.pop(name.lower(), None)
            else:
                headers[name] = value

        content, content_type = _build_request_content(
            request_blob=request_blob,
            request_content_type=request.content_type,
            json_overrides=json_overrides,
            form_overrides=form_overrides,
            body_text_override=body_text_override,
        )
        if content_type:
            headers["Content-Type"] = content_type

        experiment = Experiment(
            experiment_id=new_identifier("experiment"),
            baseline_entry_id=entry_id,
            experiment_type=ExperimentType.REPLAY,
            target_surface=_infer_target_surface(query_overrides, header_overrides, json_overrides, form_overrides),
            mutation_strategy={
                "query_overrides": query_overrides or {},
                "header_overrides": header_overrides or {},
                "json_overrides": json_overrides or {},
                "form_overrides": form_overrides or {},
                "body_text_override": body_text_override,
            },
            status="completed",
        )
        self.store.upsert_experiment(experiment)

        started_at = time.time()
        try:
            client_options: dict[str, Any] = {
                "timeout": self.config.replay_timeout_seconds,
                "follow_redirects": follow_redirects,
                "trust_env": False,
            }
            if use_proxy:
                client_options["proxy"] = self.config.charles_proxy_url
            async with httpx.AsyncClient(
                **client_options,
            ) as client:
                response = await client.request(
                    entry.method,
                    url,
                    headers=headers,
                    content=content,
                )
            elapsed_ms = int((time.time() - started_at) * 1000)
            run_status = RunExecutionStatus.SUCCEEDED
            error_class = None
            response_blob = BodyBlob(
                body_blob_id=new_identifier("blob"),
                storage_kind=BodyStorageKind.INLINE,
                byte_length=len(response.content),
                text_length=len(response.text) if response.text else None,
                sha256=hash_payload(response.content),
                is_binary=False,
                charset=response.encoding,
                raw_bytes=response.content,
                raw_text=response.text,
                preservation_level=BodyPreservationLevel.RAW,
                metadata={
                    "headers": dict(response.headers),
                    "final_url": str(response.url),
                },
            )
            self.store.upsert_body_blob(response_blob)
            diff_summary = {
                "baseline_status": entry.status_code,
                "replay_status": response.status_code,
                "status_changed": entry.status_code != response.status_code,
                "baseline_length": snapshot["response_body_blob"].byte_length if snapshot["response_body_blob"] else None,
                "replay_length": len(response.content),
            }
        except Exception as exc:
            elapsed_ms = int((time.time() - started_at) * 1000)
            run_status = RunExecutionStatus.FAILED
            error_class = type(exc).__name__
            response = None
            response_blob = None
            diff_summary = {
                "baseline_status": entry.status_code,
                "replay_status": None,
                "status_changed": True,
                "error": str(exc),
            }

        run = Run(
            run_id=new_identifier("run"),
            experiment_id=experiment.experiment_id,
            variant_label="replay",
            request_snapshot={
                "method": entry.method,
                "url": url,
                "headers": headers,
            },
            execution_status=run_status,
            response_status=response.status_code if response is not None else None,
            latency_ms=elapsed_ms,
            response_body_blob_id=response_blob.body_blob_id if response_blob else None,
            diff_summary=diff_summary,
            error_class=error_class,
        )
        self.store.upsert_run(run)

        finding = None
        if run.execution_status is RunExecutionStatus.FAILED or diff_summary["status_changed"]:
            finding = Finding(
                finding_id=new_identifier("finding"),
                subject_type=FindingSubjectType.RUN,
                subject_id=run.run_id,
                finding_type=FindingType.REPLAY_FAILURE
                if run.execution_status is RunExecutionStatus.FAILED
                else FindingType.AUTH_DEPENDENCY,
                severity="high",
                confidence=0.88,
                title="Replay diverged from baseline",
                evidence=diff_summary,
                recommendation="Inspect headers, cookies, and dynamic parameters before running mutation experiments.",
            )
            self.store.upsert_finding(finding)

        return {
            "experiment": experiment.model_dump(mode="json", exclude_none=True),
            "run": run.model_dump(mode="json", exclude_none=True),
            "response": {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body_blob_id": response_blob.body_blob_id if response_blob else None,
            }
            if response is not None
            else None,
            "finding": finding.model_dump(mode="json", exclude_none=True) if finding else None,
        }


def _build_request_content(
    *,
    request_blob: BodyBlob | None,
    request_content_type: str | None,
    json_overrides: dict[str, Any] | None,
    form_overrides: dict[str, Any] | None,
    body_text_override: str | None,
) -> tuple[bytes | None, str | None]:
    if body_text_override is not None:
        return body_text_override.encode("utf-8"), request_content_type

    base_text = request_blob.raw_text if request_blob else None
    if json_overrides is not None and base_text:
        payload = json.loads(base_text)
        if not isinstance(payload, dict):
            raise ValueError("JSON body overrides require an object payload")
        for key, value in json_overrides.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), "application/json"

    if form_overrides is not None and base_text:
        payload = {}
        for key, values in parse_qs(base_text, keep_blank_values=True).items():
            payload[key] = list(values)
        for key, value in form_overrides.items():
            if value is None:
                payload.pop(key, None)
            elif isinstance(value, list):
                payload[key] = [str(item) for item in value]
            else:
                payload[key] = [str(value)]
        encoded = urlencode(payload, doseq=True).encode("utf-8")
        return encoded, "application/x-www-form-urlencoded"

    if request_blob and request_blob.raw_bytes is not None:
        return request_blob.raw_bytes, request_content_type
    if request_blob and request_blob.raw_text is not None:
        return request_blob.raw_text.encode(request_blob.charset or "utf-8"), request_content_type
    return None, request_content_type


def _infer_target_surface(
    query_overrides: dict[str, Any] | None,
    header_overrides: dict[str, Any] | None,
    json_overrides: dict[str, Any] | None,
    form_overrides: dict[str, Any] | None,
) -> TargetSurface:
    if json_overrides:
        return TargetSurface.JSON_PATH
    if form_overrides:
        return TargetSurface.FORM_FIELD
    if query_overrides:
        return TargetSurface.QUERY
    if header_overrides:
        return TargetSurface.HEADER
    return TargetSurface.RAW_BODY


def _resolve_entry_port(metadata: dict[str, Any]) -> int | None:
    actual_port = metadata.get("actual_port")
    if isinstance(actual_port, int):
        return actual_port
    port = metadata.get("port")
    if isinstance(port, int):
        return port
    return None

