"""Query helpers for imported captures, entries, and reverse findings."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from charles_mcp.reverse.models import Entry, Finding, FindingSubjectType, FindingType
from charles_mcp.reverse.services.common import parse_request_parameters, new_identifier
from charles_mcp.reverse.storage import SQLiteStore


class QueryService:
    """Serve read-oriented workflows from the canonical store."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def list_captures(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return [
            capture.model_dump(mode="json", exclude_none=True)
            for capture in self.store.list_captures(limit=limit)
        ]

    def query_entries(
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
    ) -> dict[str, Any]:
        entries = self.store.list_entries(
            capture_id=capture_id,
            host_contains=host_contains,
            path_contains=path_contains,
            method_in=method_in,
            status_in=status_in,
            min_sequence_no=min_sequence_no,
            limit=limit,
            offset=offset,
        )
        return {
            "capture_id": capture_id,
            "items": [self.entry_summary(entry) for entry in entries],
            "returned": len(entries),
            "offset": offset,
            "limit": limit,
        }

    def get_entry_detail(self, *, entry_id: str) -> dict[str, Any]:
        snapshot = self.store.get_entry_snapshot(entry_id)
        if snapshot is None:
            raise ValueError(f"entry `{entry_id}` was not found")
        return {
            "entry": snapshot["entry"].model_dump(mode="json", exclude_none=True),
            "request": snapshot["request"].model_dump(mode="json", exclude_none=True)
            if snapshot["request"]
            else None,
            "response": snapshot["response"].model_dump(mode="json", exclude_none=True)
            if snapshot["response"]
            else None,
            "request_body_blob": snapshot["request_body_blob"].model_dump(mode="json", exclude_none=True)
            if snapshot["request_body_blob"]
            else None,
            "response_body_blob": snapshot["response_body_blob"].model_dump(mode="json", exclude_none=True)
            if snapshot["response_body_blob"]
            else None,
            "decoded_artifacts": [
                artifact.model_dump(mode="json", exclude_none=True)
                for artifact in snapshot["decoded_artifacts"]
            ],
        }

    def list_findings(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_subject = FindingSubjectType(subject_type) if subject_type else None
        findings = self.store.list_findings(subject_type=normalized_subject, subject_id=subject_id)
        return [finding.model_dump(mode="json", exclude_none=True) for finding in findings]

    def discover_signature_candidates(self, *, entry_ids: list[str]) -> dict[str, Any]:
        if len(entry_ids) < 2:
            raise ValueError("discover_signature_candidates requires at least 2 entry_ids")

        param_values: dict[str, list[str]] = defaultdict(list)
        seen_entries: list[Entry] = []
        for entry_id in entry_ids:
            snapshot = self.store.get_entry_snapshot(entry_id)
            if snapshot is None:
                raise ValueError(f"entry `{entry_id}` was not found")
            entry = snapshot["entry"]
            request = snapshot["request"]
            request_blob = snapshot["request_body_blob"]
            seen_entries.append(entry)
            request_text = request_blob.raw_text if request_blob else None
            params = parse_request_parameters(
                query=entry.query,
                request_content_type=request.content_type if request else None,
                request_text=request_text,
            )
            for key, values in params.items():
                param_values[key].append(json.dumps(values, ensure_ascii=False))

        candidates: list[dict[str, Any]] = []
        for field, values in sorted(param_values.items()):
            distinct_values = sorted(set(values))
            if len(distinct_values) <= 1:
                continue
            score = 0.4
            lowered = field.lower()
            if any(token in lowered for token in ("sign", "sig", "token", "nonce", "ts", "timestamp")):
                score += 0.35
            if all(len(value) >= 8 for value in distinct_values):
                score += 0.15
            if len(distinct_values) == len(values):
                score += 0.10
            candidates.append(
                {
                    "field": field,
                    "distinct_values": distinct_values[:5],
                    "observed_count": len(values),
                    "score": round(min(score, 0.99), 2),
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        findings: list[Finding] = []
        for candidate in candidates[:5]:
            findings.append(
                Finding(
                    finding_id=new_identifier("finding"),
                    subject_type=FindingSubjectType.ENTRY,
                    subject_id=entry_ids[0],
                    finding_type=FindingType.SIGNATURE_CANDIDATE,
                    severity="medium",
                    confidence=candidate["score"],
                    title=f"Possible signature-related field: {candidate['field']}",
                    evidence=candidate,
                    recommendation="Validate with a mutation experiment by dropping or modifying this field.",
                )
            )

        for finding in findings:
            self.store.upsert_finding(finding)

        return {
            "entry_ids": entry_ids,
            "candidates": candidates,
            "persisted_findings": len(findings),
        }

    def entry_summary(self, entry: Entry) -> dict[str, Any]:
        return {
            "entry_id": entry.entry_id,
            "sequence_no": entry.sequence_no,
            "method": entry.method,
            "host": entry.host,
            "path": entry.path,
            "query": entry.query,
            "status_code": entry.status_code,
            "timing_summary": entry.timing_summary,
            "size_summary": entry.size_summary,
            "replayability_score": entry.replayability_score,
        }

