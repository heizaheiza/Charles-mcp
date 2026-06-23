"""Module-level helpers shared by all live reverse-analysis workflows.

This file is the home for presentation, mutation-plan and replay-recipe
helpers that used to live at the bottom of workflow_service.py. They are
pure functions with no service dependencies, so any workflow strategy can
import them without circular concerns.
"""

from __future__ import annotations

from typing import Any

from charles_mcp.reverse.services.common import parse_request_parameters

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
