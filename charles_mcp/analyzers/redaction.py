"""Redaction helpers for sensitive HTTP data."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
}

SENSITIVE_BODY_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "session",
    "sessionid",
    "password",
    "passwd",
    "secret",
    "api_key",
    "client_secret",
}

REDACTED = "[REDACTED]"

_TEXT_PATTERNS = [
    re.compile(r"\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(
        r'(?i)\b(token|access_token|refresh_token|password|session|secret|api_key)\b'
        r'(["\']?\s*[:=]\s*["\']?)([^"&,\s]+)'
    ),
]


def redact_header_value(
    name: str,
    value: str | None,
    *,
    include_sensitive: bool = False,
) -> tuple[str | None, list[str]]:
    """Redact sensitive header values."""
    lower_name = name.lower()
    if include_sensitive or lower_name not in SENSITIVE_HEADER_NAMES:
        return value, []
    return REDACTED, [f"headers.{lower_name}"]


def redact_json_like(
    value: Any,
    *,
    prefix: str = "body",
    include_sensitive: bool = False,
) -> tuple[Any, list[str]]:
    """Recursively redact sensitive keys in JSON-like objects."""
    if include_sensitive:
        return value, []

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        applied: list[str] = []
        for key, item in value.items():
            key_str = str(key)
            path = f"{prefix}.{key_str}"
            if key_str.lower() in SENSITIVE_BODY_KEYS:
                redacted[key_str] = REDACTED
                applied.append(path)
                continue

            nested, nested_applied = redact_json_like(
                item,
                prefix=path,
                include_sensitive=include_sensitive,
            )
            redacted[key_str] = nested
            applied.extend(nested_applied)
        return redacted, applied

    if isinstance(value, list):
        redacted_list: list[Any] = []
        applied: list[str] = []
        for index, item in enumerate(value):
            nested, nested_applied = redact_json_like(
                item,
                prefix=f"{prefix}[{index}]",
                include_sensitive=include_sensitive,
            )
            redacted_list.append(nested)
            applied.extend(nested_applied)
        return redacted_list, applied

    return value, []


def redact_form_mapping(
    mapping: dict[str, list[str]],
    *,
    prefix: str = "body",
    include_sensitive: bool = False,
) -> tuple[dict[str, list[str]], list[str]]:
    """Redact sensitive keys in form-urlencoded data."""
    if include_sensitive:
        return mapping, []

    redacted: dict[str, list[str]] = {}
    applied: list[str] = []
    for key, values in mapping.items():
        if key.lower() in SENSITIVE_BODY_KEYS:
            redacted[key] = [REDACTED for _ in values]
            applied.append(f"{prefix}.{key}")
        else:
            redacted[key] = list(values)
    return redacted, applied


def redact_text(
    value: str,
    *,
    include_sensitive: bool = False,
) -> tuple[str, list[str]]:
    """Apply lightweight text redaction to previews."""
    if include_sensitive or not value:
        return value, []

    redacted = value
    applied: list[str] = []

    if _TEXT_PATTERNS[0].search(redacted):
        redacted = _TEXT_PATTERNS[0].sub(REDACTED, redacted)
        applied.append("text.credentials")

    def _replace(match: re.Match[str]) -> str:
        applied.append(f"text.{match.group(1).lower()}")
        return f"{match.group(1)}{match.group(2)}{REDACTED}"

    redacted = _TEXT_PATTERNS[1].sub(_replace, redacted)
    return redacted, applied
