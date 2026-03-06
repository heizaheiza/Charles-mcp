"""Helpers for traffic analysis and normalization."""

from charles_mcp.analyzers.body import normalize_body
from charles_mcp.analyzers.headers import build_header_highlights, normalize_headers
from charles_mcp.analyzers.redaction import (
    SENSITIVE_BODY_KEYS,
    SENSITIVE_HEADER_NAMES,
    redact_form_mapping,
    redact_header_value,
    redact_json_like,
    redact_text,
)
from charles_mcp.analyzers.resource_classifier import classify_entry

__all__ = [
    "SENSITIVE_BODY_KEYS",
    "SENSITIVE_HEADER_NAMES",
    "build_header_highlights",
    "classify_entry",
    "normalize_body",
    "normalize_headers",
    "redact_form_mapping",
    "redact_header_value",
    "redact_json_like",
    "redact_text",
]
