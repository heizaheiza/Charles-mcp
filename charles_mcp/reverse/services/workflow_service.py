"""High-level reverse-engineering workflows built on top of vnext primitives."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from charles_mcp.reverse.models import CaptureSourceFormat
from charles_mcp.reverse.services.common import parse_request_parameters
from charles_mcp.reverse.services.decode_service import DecodeService
from charles_mcp.reverse.services.live_analysis_service import LiveAnalysisService
from charles_mcp.reverse.services.query_service import QueryService
from charles_mcp.reverse.services.replay_service import ReplayService


_DEFAULT_LOGIN_KEYWORDS = ("login", "signin", "sign-in", "auth", "oauth", "token", "session")
_DEFAULT_API_KEYWORDS = ("api", "sdk", "gateway", "list", "detail", "query", "submit", "report")
_DEFAULT_SIGNATURE_HINTS = ("sign", "sig", "signature", "token", "nonce", "ts", "timestamp", "auth")
_DEFAULT_LOGIN_FIELD_HINTS = (
    "sign",
    "token",
    "nonce",
    "ts",
    "timestamp",
    "code",
    "password",
    "captcha",
)
_DEFAULT_LOGIN_COOKIE_HINTS = ("session", "csrf", "token", "auth")
_DEFAULT_LOGIN_HEADER_HINTS = ("authorization", "x-csrf-token", "x-auth-token", "x-session-token")
_DEFAULT_API_HEADER_HINTS = ("x-request-id", "x-device-id", "x-client-version", "x-api-version")
_DEFAULT_SIGNATURE_HEADER_HINTS = ("authorization", "x-signature", "x-auth-token", "x-ms-token")
_DEFAULT_SIGNATURE_COOKIE_HINTS = ("session", "csrf", "msToken", "token", "auth")

_LOGIN_TARGET_LIMIT = 3
_LOGIN_VARIANT_LIMIT = 6
_API_TARGET_LIMIT = 4
_API_VARIANT_LIMIT = 8
_SIGNATURE_TARGET_LIMIT = 4
_SIGNATURE_VARIANT_LIMIT = 12


class WorkflowService:
    """Compose low-level tools into task-oriented reverse-analysis workflows."""

    def __init__(
        self,
        *,
        live_service: LiveAnalysisService,
        query_service: QueryService,
        decode_service: DecodeService,
        replay_service: ReplayService,
    ) -> None:
        self.live_service = live_service
        self.query_service = query_service
        self.decode_service = decode_service
        self.replay_service = replay_service

    async def analyze_live_login_flow(
        self,
        *,
        live_session_id: str,
        snapshot_format: CaptureSourceFormat = CaptureSourceFormat.XML,
        host_contains: str | None = None,
        path_keywords: list[str] | None = None,
        limit: int = 20,
        advance: bool = True,
        decode_bodies: bool = True,
        descriptor_path: str | None = None,
        message_type: str | None = None,
        run_replay: bool = False,
        replay_json_overrides: dict[str, Any] | None = None,
        replay_use_proxy: bool = False,
    ) -> dict[str, Any]:
        """Analyze new live-session traffic and summarize login/auth-relevant requests."""
        path_keywords = path_keywords or list(_DEFAULT_LOGIN_KEYWORDS)
        live_result = await self.live_service.read(
            live_session_id=live_session_id,
            snapshot_format=snapshot_format,
            host_contains=host_contains,
            limit=limit,
            advance=advance,
        )
        items = list(live_result["items"])
        candidates = self._rank_login_candidates(items, path_keywords=path_keywords)
        return await self._build_workflow_result(
            workflow_name="login",
            live_session_id=live_session_id,
            live_result=live_result,
            items=items,
            candidates=candidates,
            path_keywords=path_keywords,
            descriptor_path=descriptor_path,
            message_type=message_type,
            decode_bodies=decode_bodies,
            run_replay=run_replay,
            replay_json_overrides=replay_json_overrides,
            replay_use_proxy=replay_use_proxy,
            no_items_headline="No new live entries matched the current snapshot window.",
            no_items_overview="The live snapshot did not contain new candidate login/auth traffic.",
            no_items_assessment="No login/auth requests were available to score.",
            no_items_actions=[
                "Trigger the target login/auth flow again.",
                "Call the workflow again after new traffic appears.",
            ],
            no_candidates_headline="New traffic was captured, but none ranked as a login/auth candidate.",
            no_candidates_overview="The snapshot contained new entries, but none met the login/auth scoring threshold.",
            no_candidates_assessment="No path/method/status combination looked sufficiently login-like.",
            no_candidates_actions=[
                "Broaden `path_keywords` or remove `host_contains` restrictions.",
                "Inspect the raw live entries to find the relevant flow manually.",
            ],
            success_headline_template="Selected `{method} {path}` as the top live login/auth candidate.",
            success_overview="The workflow identified live login/auth-like traffic, decoded the selected exchange, and summarized likely reverse-engineering next steps.",
            candidate_label="login/auth",
            summary_count_alias="login_candidate_count",
            evidence_candidates_key="login_candidates",
            mutation_policy={
                "target_limit": _LOGIN_TARGET_LIMIT,
                "variant_limit": _LOGIN_VARIANT_LIMIT,
                "field_hints": list(_DEFAULT_LOGIN_FIELD_HINTS),
                "header_hints": list(_DEFAULT_LOGIN_HEADER_HINTS),
                "cookie_hints": list(_DEFAULT_LOGIN_COOKIE_HINTS),
                "prefer_signature_fields": True,
                "operator_order": ["drop", "tamper_signature", "stale_timestamp", "remove_cookie", "remove_header"],
            },
        )

    async def analyze_live_api_flow(
        self,
        *,
        live_session_id: str,
        snapshot_format: CaptureSourceFormat = CaptureSourceFormat.XML,
        host_contains: str | None = None,
        path_keywords: list[str] | None = None,
        limit: int = 20,
        advance: bool = True,
        decode_bodies: bool = True,
        descriptor_path: str | None = None,
        message_type: str | None = None,
        run_replay: bool = False,
        replay_json_overrides: dict[str, Any] | None = None,
        replay_use_proxy: bool = False,
    ) -> dict[str, Any]:
        """Analyze new live-session traffic and summarize API-like requests."""
        path_keywords = path_keywords or list(_DEFAULT_API_KEYWORDS)
        live_result = await self.live_service.read(
            live_session_id=live_session_id,
            snapshot_format=snapshot_format,
            host_contains=host_contains,
            limit=limit,
            advance=advance,
        )
        items = list(live_result["items"])
        candidates = self._rank_api_candidates(items, path_keywords=path_keywords)
        return await self._build_workflow_result(
            workflow_name="api",
            live_session_id=live_session_id,
            live_result=live_result,
            items=items,
            candidates=candidates,
            path_keywords=path_keywords,
            descriptor_path=descriptor_path,
            message_type=message_type,
            decode_bodies=decode_bodies,
            run_replay=run_replay,
            replay_json_overrides=replay_json_overrides,
            replay_use_proxy=replay_use_proxy,
            no_items_headline="No new live entries matched the current snapshot window.",
            no_items_overview="The live snapshot did not contain new candidate API traffic.",
            no_items_assessment="No API requests were available to score.",
            no_items_actions=[
                "Trigger the target API flow again.",
                "Call the workflow again after new traffic appears.",
            ],
            no_candidates_headline="New traffic was captured, but none ranked as an API candidate.",
            no_candidates_overview="The snapshot contained new entries, but none met the API scoring threshold.",
            no_candidates_assessment="No path/method/status/content-type combination looked sufficiently API-like.",
            no_candidates_actions=[
                "Broaden `path_keywords` or remove `host_contains` restrictions.",
                "Inspect the raw live entries to find the relevant API flow manually.",
            ],
            success_headline_template="Selected `{method} {path}` as the top live API candidate.",
            success_overview="The workflow identified API-like traffic, decoded the selected exchange, and summarized likely reverse-engineering next steps.",
            candidate_label="API",
            mutation_policy={
                "target_limit": _API_TARGET_LIMIT,
                "variant_limit": _API_VARIANT_LIMIT,
                "field_hints": [],
                "header_hints": list(_DEFAULT_API_HEADER_HINTS),
                "cookie_hints": [],
                "prefer_signature_fields": False,
                "operator_order": ["drop", "empty", "zero", "false", "fixed_literal"],
            },
        )

    async def analyze_live_signature_flow(
        self,
        *,
        live_session_id: str,
        snapshot_format: CaptureSourceFormat = CaptureSourceFormat.XML,
        host_contains: str | None = None,
        path_keywords: list[str] | None = None,
        signature_hints: list[str] | None = None,
        limit: int = 20,
        advance: bool = True,
        decode_bodies: bool = True,
        descriptor_path: str | None = None,
        message_type: str | None = None,
        run_replay: bool = False,
        replay_json_overrides: dict[str, Any] | None = None,
        replay_use_proxy: bool = False,
    ) -> dict[str, Any]:
        """Analyze new live-session traffic and focus on likely signature-protected requests."""
        path_keywords = path_keywords or list(_DEFAULT_LOGIN_KEYWORDS + _DEFAULT_API_KEYWORDS)
        signature_hints = signature_hints or list(_DEFAULT_SIGNATURE_HINTS)
        live_result = await self.live_service.read(
            live_session_id=live_session_id,
            snapshot_format=snapshot_format,
            host_contains=host_contains,
            limit=limit,
            advance=advance,
        )
        items = list(live_result["items"])
        candidates = self._rank_signature_candidates(
            items,
            path_keywords=path_keywords,
            signature_hints=signature_hints,
        )
        return await self._build_workflow_result(
            workflow_name="signature",
            live_session_id=live_session_id,
            live_result=live_result,
            items=items,
            candidates=candidates,
            path_keywords=path_keywords,
            descriptor_path=descriptor_path,
            message_type=message_type,
            decode_bodies=decode_bodies,
            run_replay=run_replay,
            replay_json_overrides=replay_json_overrides,
            replay_use_proxy=replay_use_proxy,
            no_items_headline="No new live entries matched the current snapshot window.",
            no_items_overview="The live snapshot did not contain new candidate signature-bearing traffic.",
            no_items_assessment="No requests were available to score for signature behavior.",
            no_items_actions=[
                "Trigger the target signed request flow again.",
                "Call the workflow again after new traffic appears.",
            ],
            no_candidates_headline="New traffic was captured, but none ranked as a signature-analysis candidate.",
            no_candidates_overview="The snapshot contained new entries, but none showed strong signature-like characteristics.",
            no_candidates_assessment="No request had enough body/status/path signal to justify signature analysis.",
            no_candidates_actions=[
                "Capture more examples of the same endpoint with varying inputs.",
                "Broaden the keyword set or inspect raw entries manually.",
            ],
            success_headline_template="Selected `{method} {path}` as the top live signature-analysis candidate.",
            success_overview="The workflow identified likely signature-sensitive traffic, decoded the selected exchange, and summarized likely reverse-engineering next steps.",
            candidate_label="signature-sensitive",
            mutation_policy={
                "target_limit": _SIGNATURE_TARGET_LIMIT,
                "variant_limit": _SIGNATURE_VARIANT_LIMIT,
                "field_hints": list(signature_hints),
                "header_hints": list(_DEFAULT_SIGNATURE_HEADER_HINTS),
                "cookie_hints": list(_DEFAULT_SIGNATURE_COOKIE_HINTS),
                "prefer_signature_fields": True,
                "operator_order": ["drop", "tamper_signature", "stale_timestamp", "replay_previous_value", "remove_header", "remove_cookie"],
            },
            extra_summary={"signature_hints": signature_hints},
        )

    def _rank_login_candidates(self, items: list[dict[str, Any]], *, path_keywords: list[str]) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for item in items:
            path = (item.get("path") or "").lower()
            method = (item.get("method") or "").upper()
            status_code = item.get("status_code")
            score = 0
            reasons: list[str] = []
            if any(keyword.lower() in path for keyword in path_keywords):
                score += 5
                reasons.append("path matches login/auth keyword")
            if method == "POST":
                score += 3
                reasons.append("POST request")
            if status_code in {200, 201, 302, 401, 403}:
                score += 2
                reasons.append("login-like response status")
            if item.get("size_summary", {}).get("request_body_bytes"):
                score += 1
                reasons.append("request has body")
            if score <= 0:
                continue
            candidate = dict(item)
            candidate["score"] = score
            candidate["reasons"] = reasons
            ranked.append(candidate)
        ranked.sort(key=lambda item: (item["score"], item.get("sequence_no", 0)), reverse=True)
        return ranked

    def _rank_api_candidates(self, items: list[dict[str, Any]], *, path_keywords: list[str]) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for item in items:
            path = (item.get("path") or "").lower()
            method = (item.get("method") or "").upper()
            status_code = item.get("status_code")
            size_summary = item.get("size_summary", {})
            score = 0
            reasons: list[str] = []
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                score += 4
                reasons.append("mutating HTTP method")
            elif method == "GET":
                score += 1
                reasons.append("read-only HTTP method")
            if any(keyword.lower() in path for keyword in path_keywords):
                score += 3
                reasons.append("path matches API keyword")
            if status_code in {200, 201, 202, 204}:
                score += 3
                reasons.append("successful API response status")
            elif status_code in {400, 404, 409, 429}:
                score += 1
                reasons.append("client-visible API error status")
            elif status_code in {401, 403}:
                reasons.append("auth-style status kept but not preferred for generic API flow")
            if size_summary.get("request_body_bytes"):
                score += 2
                reasons.append("request has body")
            if size_summary.get("response_body_bytes"):
                score += 1
                reasons.append("response has body")
            if any(hint in path for hint in _DEFAULT_SIGNATURE_HINTS):
                score -= 3
                reasons.append("deprioritized because path looks signature/auth specific")
            if score <= 0:
                continue
            candidate = dict(item)
            candidate["score"] = score
            candidate["reasons"] = reasons
            ranked.append(candidate)
        ranked.sort(key=lambda item: (item["score"], item.get("sequence_no", 0)), reverse=True)
        return ranked

    def _rank_signature_candidates(
        self,
        items: list[dict[str, Any]],
        *,
        path_keywords: list[str],
        signature_hints: list[str],
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for item in items:
            path = (item.get("path") or "").lower()
            method = (item.get("method") or "").upper()
            status_code = item.get("status_code")
            size_summary = item.get("size_summary", {})
            score = 0
            reasons: list[str] = []
            if method in {"POST", "PUT", "PATCH"}:
                score += 4
                reasons.append("mutable request likely to carry dynamic parameters")
            if any(keyword.lower() in path for keyword in path_keywords):
                score += 2
                reasons.append("path matches workflow keyword")
            if any(hint.lower() in path for hint in signature_hints):
                score += 3
                reasons.append("path contains signature-like hint")
            if status_code in {401, 403}:
                score += 4
                reasons.append("authorization-style status code")
            elif status_code in {200, 302}:
                score += 1
                reasons.append("success status often useful for baseline comparison")
            if size_summary.get("request_body_bytes"):
                score += 2
                reasons.append("request has body")
            if score <= 0:
                continue
            candidate = dict(item)
            candidate["score"] = score
            candidate["reasons"] = reasons
            ranked.append(candidate)
        ranked.sort(key=lambda item: (item["score"], item.get("sequence_no", 0)), reverse=True)
        return ranked

    def _safe_decode(
        self,
        *,
        entry_id: str,
        side: str,
        descriptor_path: str | None,
        message_type: str | None,
    ) -> dict[str, Any] | None:
        try:
            return self.decode_service.decode_entry_body(
                entry_id=entry_id,
                side=side,
                descriptor_path=descriptor_path,
                message_type=message_type,
            )
        except Exception as exc:
            return {"entry_id": entry_id, "side": side, "decode_error": str(exc)}

    async def _build_workflow_result(
        self,
        *,
        workflow_name: str,
        live_session_id: str,
        live_result: dict[str, Any],
        items: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        path_keywords: list[str],
        descriptor_path: str | None,
        message_type: str | None,
        decode_bodies: bool,
        run_replay: bool,
        replay_json_overrides: dict[str, Any] | None,
        replay_use_proxy: bool,
        no_items_headline: str,
        no_items_overview: str,
        no_items_assessment: str,
        no_items_actions: list[str],
        no_candidates_headline: str,
        no_candidates_overview: str,
        no_candidates_assessment: str,
        no_candidates_actions: list[str],
        success_headline_template: str,
        success_overview: str,
        candidate_label: str,
        summary_count_alias: str | None = None,
        evidence_candidates_key: str = "candidates",
        mutation_policy: dict[str, Any],
        extra_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        extra_summary = extra_summary or {}
        if not items:
            empty_plan = _empty_mutation_plan(workflow_name)
            return {
                "live_session_id": live_session_id,
                "capture_id": live_result["capture_id"],
                "analysis_status": "no_new_entries",
                "summary": {
                    "headline": no_items_headline,
                    "new_transaction_count": live_result["new_transaction_count"],
                    "items_considered": 0,
                    "candidate_count": 0,
                    "selected_entry_id": None,
                    "signature_candidate_fields": [],
                    "replay_outcome": None,
                    **({summary_count_alias: 0} if summary_count_alias else {}),
                    "mutation_plan_overview": _mutation_plan_overview(empty_plan),
                    **extra_summary,
                },
                "report": {
                    "overview": no_items_overview,
                    "candidate_assessment": no_items_assessment,
                    "selected_request": None,
                    "decoded_observations": [],
                    "signature_analysis": None,
                    "replay_analysis": None,
                    "mutation_strategy": _mutation_strategy_text(empty_plan),
                    "recommended_next_actions": no_items_actions,
                },
                "evidence": {
                    "workflow": workflow_name,
                    "path_keywords": path_keywords,
                    "live_read": live_result,
                    evidence_candidates_key: [],
                    "selected_entry_detail": None,
                    "decoded_request": None,
                    "decoded_response": None,
                    "signature_candidates": None,
                    "replay_result": None,
                    "related_findings": [],
                    "mutation_plan": empty_plan,
                },
            }

        if not candidates:
            empty_plan = _empty_mutation_plan(workflow_name)
            return {
                "live_session_id": live_session_id,
                "capture_id": live_result["capture_id"],
                "analysis_status": f"no_{workflow_name}_candidates",
                "summary": {
                    "headline": no_candidates_headline,
                    "new_transaction_count": live_result["new_transaction_count"],
                    "items_considered": len(items),
                    "candidate_count": 0,
                    "selected_entry_id": None,
                    "signature_candidate_fields": [],
                    "replay_outcome": None,
                    **({summary_count_alias: 0} if summary_count_alias else {}),
                    "mutation_plan_overview": _mutation_plan_overview(empty_plan),
                    **extra_summary,
                },
                "report": {
                    "overview": no_candidates_overview,
                    "candidate_assessment": no_candidates_assessment,
                    "selected_request": None,
                    "decoded_observations": [],
                    "signature_analysis": None,
                    "replay_analysis": None,
                    "mutation_strategy": _mutation_strategy_text(empty_plan),
                    "recommended_next_actions": no_candidates_actions,
                },
                "evidence": {
                    "workflow": workflow_name,
                    "path_keywords": path_keywords,
                    "live_read": live_result,
                    evidence_candidates_key: [],
                    "selected_entry_detail": None,
                    "decoded_request": None,
                    "decoded_response": None,
                    "signature_candidates": None,
                    "replay_result": None,
                    "related_findings": [],
                    "mutation_plan": empty_plan,
                },
            }

        selected = candidates[0]
        selected_entry_id = selected["entry_id"]
        selected_detail = self.query_service.get_entry_detail(entry_id=selected_entry_id)
        decoded_request = None
        decoded_response = None
        if decode_bodies:
            decoded_request = self._safe_decode(
                entry_id=selected_entry_id,
                side="request",
                descriptor_path=descriptor_path,
                message_type=message_type,
            )
            decoded_response = self._safe_decode(
                entry_id=selected_entry_id,
                side="response",
                descriptor_path=descriptor_path,
                message_type=message_type,
            )

        compare_ids = [candidate["entry_id"] for candidate in candidates[: min(3, len(candidates))]]
        signature_candidates = None
        if len(compare_ids) >= 2:
            signature_candidates = self.query_service.discover_signature_candidates(entry_ids=compare_ids)

        replay_result = None
        if run_replay:
            replay_result = await self.replay_service.replay_entry(
                entry_id=selected_entry_id,
                json_overrides=replay_json_overrides,
                use_proxy=replay_use_proxy,
            )

        related_findings = self.query_service.list_findings(subject_id=selected_entry_id)
        if replay_result and replay_result.get("run"):
            related_findings.extend(
                self.query_service.list_findings(
                    subject_type="run",
                    subject_id=replay_result["run"]["run_id"],
                )
            )

        signature_fields = []
        if signature_candidates is not None:
            signature_fields = [
                item["field"]
                for item in signature_candidates.get("candidates", [])[:5]
            ]

        replay_outcome = None
        if replay_result is not None:
            replay_outcome = {
                "status": replay_result["run"]["execution_status"],
                "baseline_status": replay_result["run"]["diff_summary"].get("baseline_status"),
                "replay_status": replay_result["run"]["diff_summary"].get("replay_status"),
                "status_changed": replay_result["run"]["diff_summary"].get("status_changed"),
            }

        mutation_plan = _build_mutation_plan(
            workflow_name=workflow_name,
            selected_entry_detail=selected_detail,
            signature_candidates=signature_candidates,
            related_findings=related_findings,
            mutation_policy=mutation_policy,
        )

        return {
            "live_session_id": live_session_id,
            "capture_id": live_result["capture_id"],
            "analysis_status": "ok",
            "summary": {
                "headline": success_headline_template.format(
                    method=selected_detail["entry"]["method"],
                    path=selected_detail["entry"]["path"],
                ),
                "new_transaction_count": live_result["new_transaction_count"],
                "items_considered": len(items),
                "candidate_count": len(candidates),
                "selected_entry_id": selected_entry_id,
                "signature_candidate_fields": signature_fields,
                "replay_outcome": replay_outcome,
                **({summary_count_alias: len(candidates)} if summary_count_alias else {}),
                "mutation_plan_overview": _mutation_plan_overview(mutation_plan),
                **extra_summary,
            },
            "report": {
                "overview": success_overview,
                "candidate_assessment": (
                    f"Scored {len(candidates)} {candidate_label} candidate(s); "
                    f"selected `{selected_entry_id}` with score {selected['score']}."
                ),
                "selected_request": _build_selected_request_summary(candidate=selected, detail=selected_detail),
                "decoded_observations": _collect_decode_observations(
                    decoded_request=decoded_request,
                    decoded_response=decoded_response,
                ),
                "signature_analysis": _build_signature_report(signature_candidates),
                "replay_analysis": _build_replay_report(replay_result),
                "mutation_strategy": _mutation_strategy_text(mutation_plan),
                "recommended_next_actions": _build_next_actions(
                    signature_candidates=signature_candidates,
                    replay_result=replay_result,
                    decoded_request=decoded_request,
                    decoded_response=decoded_response,
                ),
            },
            "evidence": {
                "workflow": workflow_name,
                "path_keywords": path_keywords,
                evidence_candidates_key: candidates,
                "live_read": live_result,
                "selected_entry_detail": selected_detail,
                "decoded_request": decoded_request,
                "decoded_response": decoded_response,
                "signature_candidates": signature_candidates,
                "replay_result": replay_result,
                "related_findings": related_findings,
                "mutation_plan": mutation_plan,
            },
        }


def _build_selected_request_summary(
    *,
    candidate: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, Any]:
    entry = detail["entry"]
    request = detail["request"] or {}
    response = detail["response"] or {}
    return {
        "entry_id": entry["entry_id"],
        "method": entry["method"],
        "host": entry["host"],
        "path": entry["path"],
        "status_code": entry["status_code"],
        "score": candidate["score"],
        "reasons": candidate["reasons"],
        "request_content_type": request.get("content_type"),
        "response_content_type": response.get("content_type"),
        "request_body_bytes": entry.get("size_summary", {}).get("request_body_bytes"),
        "response_body_bytes": entry.get("size_summary", {}).get("response_body_bytes"),
    }


def _collect_decode_observations(
    *,
    decoded_request: dict[str, Any] | None,
    decoded_response: dict[str, Any] | None,
) -> list[str]:
    observations: list[str] = []
    for side, payload in (("request", decoded_request), ("response", decoded_response)):
        if not payload:
            continue
        if "decode_error" in payload:
            observations.append(f"{side} decode failed: {payload['decode_error']}")
            continue
        observations.append(f"{side} decoded as `{payload.get('artifact_type')}`")
        for warning in payload.get("warnings") or []:
            observations.append(f"{side} warning: {warning}")
    return observations


def _build_signature_report(signature_candidates: dict[str, Any] | None) -> dict[str, Any] | None:
    if signature_candidates is None:
        return None
    return {
        "candidate_count": len(signature_candidates.get("candidates", [])),
        "top_fields": signature_candidates.get("candidates", [])[:5],
    }


def _build_replay_report(replay_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if replay_result is None:
        return None
    run = replay_result.get("run", {})
    diff = run.get("diff_summary", {})
    return {
        "execution_status": run.get("execution_status"),
        "baseline_status": diff.get("baseline_status"),
        "replay_status": diff.get("replay_status"),
        "status_changed": diff.get("status_changed"),
        "error": diff.get("error"),
    }


def _build_next_actions(
    *,
    signature_candidates: dict[str, Any] | None,
    replay_result: dict[str, Any] | None,
    decoded_request: dict[str, Any] | None,
    decoded_response: dict[str, Any] | None,
) -> list[str]:
    actions: list[str] = []
    if signature_candidates and signature_candidates.get("candidates"):
        actions.append(f"Run a focused mutation experiment on `{signature_candidates['candidates'][0]['field']}`.")
    if replay_result and replay_result.get("response", {}).get("status_code") is not None:
        actions.append(
            f"Compare baseline and replay responses around status `{replay_result['response']['status_code']}`."
        )
    if decoded_request and "decode_error" in decoded_request:
        actions.append("Inspect the raw request body because structured decode failed.")
    if decoded_response and "decode_error" in decoded_response:
        actions.append("Inspect the raw response body because structured decode failed.")
    if not actions:
        actions.append("Use the selected request as the baseline for deeper reverse analysis.")
    return actions


def _empty_mutation_plan(workflow_name: str) -> dict[str, Any]:
    return {
        "baseline_entry_id": None,
        "workflow": workflow_name,
        "selection_basis": [],
        "targets": [],
        "variants": [],
        "execution_order": [],
        "safety_notes": [
            "Do not mutate multiple high-risk fields at once.",
            "Header and cookie mutations can invalidate the full session.",
        ],
    }


def _mutation_plan_overview(mutation_plan: dict[str, Any]) -> dict[str, Any]:
    targets = mutation_plan.get("targets", [])
    variants = mutation_plan.get("variants", [])
    return {
        "candidate_target_count": len(targets),
        "planned_variant_count": len(variants),
        "top_targets": [
            {
                "field": target["field"],
                "surface": target["surface"],
                "priority": target["priority"],
            }
            for target in targets[:3]
        ],
        "primary_surface": targets[0]["surface"] if targets else None,
    }


def _mutation_strategy_text(mutation_plan: dict[str, Any]) -> str:
    if not mutation_plan.get("targets"):
        return "No mutation plan was generated for the current workflow output."
    top_fields = ", ".join(f"`{target['field']}`" for target in mutation_plan["targets"][:3])
    return (
        f"Prioritize {len(mutation_plan['variants'])} planned mutations across "
        f"{len(mutation_plan['targets'])} target(s). Start with {top_fields} "
        "and execute variants in the provided order."
    )


def _build_mutation_plan(
    *,
    workflow_name: str,
    selected_entry_detail: dict[str, Any],
    signature_candidates: dict[str, Any] | None,
    related_findings: list[dict[str, Any]],
    mutation_policy: dict[str, Any],
) -> dict[str, Any]:
    entry = selected_entry_detail["entry"]
    request = selected_entry_detail.get("request") or {}
    request_blob = selected_entry_detail.get("request_body_blob") or {}
    request_text = request_blob.get("raw_text")
    request_content_type = request.get("content_type")
    params = parse_request_parameters(
        query=entry.get("query"),
        request_content_type=request_content_type,
        request_text=request_text,
    )
    headers = request.get("headers") or {}
    cookies = request.get("cookies") or {}
    signature_field_map = {
        item["field"]: item
        for item in (signature_candidates or {}).get("candidates", [])
    }

    targets: list[dict[str, Any]] = []
    selection_basis: list[str] = []

    for field, values in params.items():
        surface = _surface_from_field(field)
        score = 0
        reasons: list[str] = []
        expected_signal = "status_change"
        lowered = field.lower()

        if field in signature_field_map:
            score += 100
            reasons.append("top signature candidate")
            selection_basis.append(f"signature candidate: {field}")
        if any(hint.lower() in lowered for hint in mutation_policy["field_hints"]):
            score += 40
            reasons.append("field name matches workflow hint")
            selection_basis.append(f"field hint match: {field}")
        if surface in {"query", "json_path", "form_field"}:
            score += 10
            reasons.append("request parameter can be replayed directly")
        if len(set(values)) > 1:
            score += 5
            reasons.append("multiple observed values")
        if workflow_name == "api" and any(hint in lowered for hint in _DEFAULT_SIGNATURE_HINTS):
            score -= 30
            reasons.append("deprioritized in API workflow because field looks signature-specific")
        if workflow_name == "signature" and any(hint in lowered for hint in _DEFAULT_SIGNATURE_HINTS):
            score += 20
            expected_signal = "auth_failure"
        if any(token in lowered for token in ("ts", "timestamp")):
            expected_signal = "auth_failure"
        if any(token in lowered for token in ("page", "offset", "limit", "sort", "feature")):
            expected_signal = "body_diff"

        if score <= 0:
            continue

        targets.append(
            {
                "target_id": _target_id(surface, field),
                "surface": surface,
                "field": field,
                "score": score,
                "reason": "; ".join(dict.fromkeys(reasons)),
                "observed_values": values[:5],
                "expected_signal": expected_signal,
            }
        )

    for header_name, values in headers.items():
        lowered = header_name.lower()
        if not any(hint in lowered for hint in mutation_policy["header_hints"]):
            continue
        targets.append(
            {
                "target_id": _target_id("header", lowered),
                "surface": "header",
                "field": lowered,
                "score": 55 if workflow_name != "api" else 35,
                "reason": "header name looks auth/signature/session related",
                "observed_values": values[:3],
                "expected_signal": "auth_failure",
            }
        )
        selection_basis.append(f"header heuristic: {lowered}")

    for cookie_name, value in cookies.items():
        lowered = cookie_name.lower()
        if not any(hint.lower() in lowered for hint in mutation_policy["cookie_hints"]):
            continue
        targets.append(
            {
                "target_id": _target_id("cookie", lowered),
                "surface": "cookie",
                "field": lowered,
                "score": 50 if workflow_name != "api" else 30,
                "reason": "cookie name looks auth/signature/session related",
                "observed_values": [value],
                "expected_signal": "auth_failure",
            }
        )
        selection_basis.append(f"cookie heuristic: {lowered}")

    if request_text:
        targets.append(
            {
                "target_id": _target_id("raw_body", "__raw_body__"),
                "surface": "raw_body",
                "field": "__raw_body__",
                "score": 20,
                "reason": "raw body fallback mutation when direct field mutations are insufficient",
                "observed_values": [request_text[:120]],
                "expected_signal": "body_diff",
            }
        )

    targets.sort(key=lambda item: (item["score"], item["field"]), reverse=True)
    targets = targets[: mutation_policy["target_limit"]]
    _assign_priority(targets)

    variants: list[dict[str, Any]] = []
    for target in targets:
        variants.extend(
            _variants_for_target(
                target=target,
                mutation_policy=mutation_policy,
                cookies=cookies,
                request_text=request_text,
            )
        )

    variants = variants[: mutation_policy["variant_limit"]]
    return {
        "baseline_entry_id": entry["entry_id"],
        "workflow": workflow_name,
        "selection_basis": list(dict.fromkeys(selection_basis))[:10],
        "targets": targets,
        "variants": variants,
        "execution_order": [variant["variant_id"] for variant in variants],
        "safety_notes": [
            "Do not mutate multiple high-risk fields at once.",
            "Header and cookie mutations can invalidate the full session.",
            "Execute variants in the provided order and compare one replay at a time.",
        ],
    }


def _surface_from_field(field: str) -> str:
    if field.startswith("query."):
        return "query"
    if field.startswith("json."):
        return "json_path"
    if field.startswith("form."):
        return "form_field"
    return "raw_body"


def _target_id(surface: str, field: str) -> str:
    return f"{surface}:{field}"


def _assign_priority(targets: list[dict[str, Any]]) -> None:
    for index, target in enumerate(targets):
        target["priority"] = "high" if index == 0 else "medium" if index <= 2 else "low"
        target.pop("score", None)


def _variants_for_target(
    *,
    target: dict[str, Any],
    mutation_policy: dict[str, Any],
    cookies: dict[str, Any],
    request_text: str | None,
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for mutation_type in mutation_policy["operator_order"]:
        recipe = _build_replay_recipe(
            surface=target["surface"],
            field=target["field"],
            mutation_type=mutation_type,
            observed_values=target.get("observed_values", []),
            cookies=cookies,
            request_text=request_text,
        )
        if recipe is None:
            continue
        variants.append(
            {
                "variant_id": f"{target['target_id']}:{mutation_type}",
                "target_id": target["target_id"],
                "name": f"{target['field']}:{mutation_type}",
                "mutation_type": mutation_type,
                "replay_recipe": recipe,
                "assertions": [
                    target["expected_signal"],
                    "status_code_delta",
                    "response_body_delta",
                ],
            }
        )
        if len(variants) >= 3:
            break
    return variants


def _build_replay_recipe(
    *,
    surface: str,
    field: str,
    mutation_type: str,
    observed_values: list[str],
    cookies: dict[str, Any],
    request_text: str | None,
) -> dict[str, Any] | None:
    if surface in {"query", "json_path", "form_field"}:
        key = field.split(".", 1)[1]
        container = {
            "query": "query_overrides",
            "json_path": "json_overrides",
            "form_field": "form_overrides",
        }[surface]
        return {container: {key: _mutation_value(mutation_type, observed_values)}}

    if surface == "header":
        value = None if mutation_type == "remove_header" else _mutation_value(mutation_type, observed_values)
        return {"header_overrides": {field: value}}

    if surface == "cookie":
        if mutation_type not in {"remove_cookie", "empty", "fixed_literal"}:
            return None
        mutated_cookies = dict(cookies)
        if mutation_type == "remove_cookie":
            mutated_cookies.pop(field, None)
        elif mutation_type == "empty":
            mutated_cookies[field] = ""
        else:
            mutated_cookies[field] = "fixed-literal"
        cookie_header = "; ".join(f"{name}={value}" for name, value in mutated_cookies.items())
        return {"header_overrides": {"cookie": cookie_header}}

    if surface == "raw_body":
        if mutation_type == "empty":
            return {"body_text_override": ""}
        if mutation_type == "fixed_literal":
            return {"body_text_override": request_text or "{}"}
        return None

    return None


def _mutation_value(mutation_type: str, observed_values: list[str]) -> Any:
    if mutation_type == "drop":
        return None
    if mutation_type == "empty":
        return ""
    if mutation_type == "zero":
        return 0
    if mutation_type == "false":
        return False
    if mutation_type == "null_like":
        return "null"
    if mutation_type == "stale_timestamp":
        return "1700000000"
    if mutation_type == "fixed_literal":
        return "fixed-literal"
    if mutation_type == "replay_previous_value":
        return observed_values[0] if observed_values else "replay-previous"
    if mutation_type == "tamper_signature":
        return "tampered-signature"
    return "fixed-literal"

