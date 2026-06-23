"""Generic API live reverse-analysis workflow."""

from __future__ import annotations

from typing import Any

from charles_mcp.reverse.services.workflows._base import _BaseLiveWorkflow
from charles_mcp.reverse.services.workflows._shared import (
    _API_TARGET_LIMIT,
    _API_VARIANT_LIMIT,
    _DEFAULT_API_HEADER_HINTS,
    _DEFAULT_API_KEYWORDS,
    _DEFAULT_SIGNATURE_HINTS,
)


class ApiWorkflow(_BaseLiveWorkflow):
    """Score live traffic for generic API requests and assemble a mutation plan."""

    workflow_name = "api"
    default_path_keywords = _DEFAULT_API_KEYWORDS
    candidate_label = "API"

    success_headline_template = "Selected `{method} {path}` as the top live API candidate."
    success_overview = (
        "The workflow identified API-like traffic, decoded the selected exchange, "
        "and summarized likely reverse-engineering next steps."
    )

    no_items_headline = "No new live entries matched the current snapshot window."
    no_items_overview = "The live snapshot did not contain new candidate API traffic."
    no_items_assessment = "No API requests were available to score."
    no_items_actions = [
        "Trigger the target API flow again.",
        "Call the workflow again after new traffic appears.",
    ]

    no_candidates_headline = "New traffic was captured, but none ranked as an API candidate."
    no_candidates_overview = (
        "The snapshot contained new entries, but none met the API scoring threshold."
    )
    no_candidates_assessment = (
        "No path/method/status/content-type combination looked sufficiently API-like."
    )
    no_candidates_actions = [
        "Broaden `path_keywords` or remove `host_contains` restrictions.",
        "Inspect the raw live entries to find the relevant API flow manually.",
    ]

    mutation_policy: dict[str, Any] = {
        "target_limit": _API_TARGET_LIMIT,
        "variant_limit": _API_VARIANT_LIMIT,
        "field_hints": [],
        "header_hints": list(_DEFAULT_API_HEADER_HINTS),
        "cookie_hints": [],
        "prefer_signature_fields": False,
        "operator_order": ["drop", "empty", "zero", "false", "fixed_literal"],
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
