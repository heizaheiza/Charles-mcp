"""Signature / dynamic parameter live reverse-analysis workflow."""

from __future__ import annotations

from typing import Any

from charles_mcp.reverse.services.workflows._base import _BaseLiveWorkflow
from charles_mcp.reverse.services.workflows._shared import (
    _DEFAULT_API_KEYWORDS,
    _DEFAULT_LOGIN_KEYWORDS,
    _DEFAULT_SIGNATURE_COOKIE_HINTS,
    _DEFAULT_SIGNATURE_HEADER_HINTS,
    _DEFAULT_SIGNATURE_HINTS,
    _SIGNATURE_TARGET_LIMIT,
    _SIGNATURE_VARIANT_LIMIT,
)


class SignatureWorkflow(_BaseLiveWorkflow):
    """Score live traffic for signature-protected requests and assemble a mutation plan."""

    workflow_name = "signature"
    # signature flow covers both login-style and api-style traffic by default
    default_path_keywords = tuple(_DEFAULT_LOGIN_KEYWORDS) + tuple(_DEFAULT_API_KEYWORDS)
    candidate_label = "signature-sensitive"

    success_headline_template = (
        "Selected `{method} {path}` as the top live signature-analysis candidate."
    )
    success_overview = (
        "The workflow identified likely signature-sensitive traffic, decoded the selected "
        "exchange, and summarized likely reverse-engineering next steps."
    )

    no_items_headline = "No new live entries matched the current snapshot window."
    no_items_overview = (
        "The live snapshot did not contain new candidate signature-bearing traffic."
    )
    no_items_assessment = "No requests were available to score for signature behavior."
    no_items_actions = [
        "Trigger the target signed request flow again.",
        "Call the workflow again after new traffic appears.",
    ]

    no_candidates_headline = (
        "New traffic was captured, but none ranked as a signature-analysis candidate."
    )
    no_candidates_overview = (
        "The snapshot contained new entries, but none showed strong signature-like characteristics."
    )
    no_candidates_assessment = (
        "No request had enough body/status/path signal to justify signature analysis."
    )
    no_candidates_actions = [
        "Capture more examples of the same endpoint with varying inputs.",
        "Broaden the keyword set or inspect raw entries manually.",
    ]

    # Base mutation policy; signature_hints from the runtime call override
    # the field_hints list via _resolve_mutation_policy.
    mutation_policy: dict[str, Any] = {
        "target_limit": _SIGNATURE_TARGET_LIMIT,
        "variant_limit": _SIGNATURE_VARIANT_LIMIT,
        "field_hints": list(_DEFAULT_SIGNATURE_HINTS),
        "header_hints": list(_DEFAULT_SIGNATURE_HEADER_HINTS),
        "cookie_hints": list(_DEFAULT_SIGNATURE_COOKIE_HINTS),
        "prefer_signature_fields": True,
        "operator_order": [
            "drop",
            "tamper_signature",
            "stale_timestamp",
            "replay_previous_value",
            "remove_header",
            "remove_cookie",
        ],
    }

    def _resolve_mutation_policy(self, **extra: Any) -> dict[str, Any]:
        """Inject runtime signature_hints into the policy's field_hints."""
        signature_hints = extra.get("signature_hints") or list(_DEFAULT_SIGNATURE_HINTS)
        policy = dict(self.mutation_policy)
        policy["field_hints"] = list(signature_hints)
        return policy

    def _extra_summary(self, **extra: Any) -> dict[str, Any]:
        signature_hints = extra.get("signature_hints") or list(_DEFAULT_SIGNATURE_HINTS)
        return {"signature_hints": list(signature_hints)}

    def _rank_candidates(
        self,
        items: list[dict[str, Any]],
        *,
        path_keywords: list[str],
        **extra: Any,
    ) -> list[dict[str, Any]]:
        signature_hints = extra.get("signature_hints") or list(_DEFAULT_SIGNATURE_HINTS)
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
