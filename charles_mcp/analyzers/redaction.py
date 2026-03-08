"""Deprecated compatibility helpers for historical redaction APIs.

The project no longer redacts traffic content. These helpers remain as no-op
shims so existing imports and parameters continue to work without changing the
returned payload.
"""

from __future__ import annotations

from typing import Any

SENSITIVE_HEADER_NAMES: set[str] = set()
SENSITIVE_BODY_KEYS: set[str] = set()
REDACTED = "[REDACTED]"


def redact_header_value(
    name: str,
    value: str | None,
    *,
    include_sensitive: bool = False,
) -> tuple[str | None, list[str]]:
    """Preserve header values.

    `include_sensitive` is retained for backward compatibility and ignored.
    """
    return value, []


def redact_json_like(
    value: Any,
    *,
    prefix: str = "body",
    include_sensitive: bool = False,
) -> tuple[Any, list[str]]:
    """Preserve JSON-like values.

    `include_sensitive` is retained for backward compatibility and ignored.
    """
    return value, []


def redact_form_mapping(
    mapping: dict[str, list[str]],
    *,
    prefix: str = "body",
    include_sensitive: bool = False,
) -> tuple[dict[str, list[str]], list[str]]:
    """Preserve form data.

    `include_sensitive` is retained for backward compatibility and ignored.
    """
    return dict(mapping), []


def redact_text(
    value: str,
    *,
    include_sensitive: bool = False,
) -> tuple[str, list[str]]:
    """Preserve text previews.

    `include_sensitive` is retained for backward compatibility and ignored.
    """
    return value, []
