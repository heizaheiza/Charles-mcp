"""Login / authentication live reverse-analysis workflow."""

from __future__ import annotations

from typing import Any

from charles_mcp.reverse.services.workflows._base import _BaseLiveWorkflow
from charles_mcp.reverse.services.workflows._shared import (
    _DEFAULT_LOGIN_COOKIE_HINTS,
    _DEFAULT_LOGIN_FIELD_HINTS,
    _DEFAULT_LOGIN_HEADER_HINTS,
    _DEFAULT_LOGIN_KEYWORDS,
    _LOGIN_TARGET_LIMIT,
    _LOGIN_VARIANT_LIMIT,
)


class LoginWorkflow(_BaseLiveWorkflow):
    """Score live traffic for login / auth requests and assemble a mutation plan."""

    workflow_name = "login"
    default_path_keywords = _DEFAULT_LOGIN_KEYWORDS
    candidate_label = "login/auth"
    summary_count_alias = "login_candidate_count"
    evidence_candidates_key = "login_candidates"

    success_headline_template = "Selected `{method} {path}` as the top live login/auth candidate."
    success_overview = (
        "The workflow identified live login/auth-like traffic, decoded the selected "
        "exchange, and summarized likely reverse-engineering next steps."
    )

    no_items_headline = "No new live entries matched the current snapshot window."
    no_items_overview = "The live snapshot did not contain new candidate login/auth traffic."
    no_items_assessment = "No login/auth requests were available to score."
    no_items_actions = [
        "Trigger the target login/auth flow again.",
        "Call the workflow again after new traffic appears.",
    ]

    no_candidates_headline = "New traffic was captured, but none ranked as a login/auth candidate."
    no_candidates_overview = (
        "The snapshot contained new entries, but none met the login/auth scoring threshold."
    )
    no_candidates_assessment = "No path/method/status combination looked sufficiently login-like."
    no_candidates_actions = [
        "Broaden `path_keywords` or remove `host_contains` restrictions.",
        "Inspect the raw live entries to find the relevant flow manually.",
    ]

    mutation_policy: dict[str, Any] = {
        "target_limit": _LOGIN_TARGET_LIMIT,
        "variant_limit": _LOGIN_VARIANT_LIMIT,
        "field_hints": list(_DEFAULT_LOGIN_FIELD_HINTS),
        "header_hints": list(_DEFAULT_LOGIN_HEADER_HINTS),
        "cookie_hints": list(_DEFAULT_LOGIN_COOKIE_HINTS),
        "prefer_signature_fields": True,
        "operator_order": [
            "drop",
            "tamper_signature",
            "stale_timestamp",
            "remove_cookie",
            "remove_header",
        ],
    }

    def _rank_candidates(
        self,
        items: list[dict[str, Any]],
        *,
        path_keywords: list[str],
        **extra: Any,
    ) -> list[dict[str, Any]]:
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
