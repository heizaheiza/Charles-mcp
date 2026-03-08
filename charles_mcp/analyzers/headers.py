"""Header normalization helpers."""

from __future__ import annotations

from collections import OrderedDict

from charles_mcp.schemas.traffic import HeaderKV

_HIGHLIGHT_ORDER = (
    "content-type",
    "accept",
    "authorization",
    "cookie",
    "set-cookie",
    "x-requested-with",
    "sec-fetch-mode",
    "sec-fetch-dest",
    "origin",
    "referer",
)


def normalize_headers(
    raw_headers: list[dict] | None,
    *,
    include_sensitive: bool = False,
) -> tuple[list[HeaderKV], dict[str, list[str]], list[str]]:
    """Normalize Charles header list into typed models and a lowercase map.

    `include_sensitive` is kept for tool compatibility and no longer affects the
    returned headers.
    """
    headers: list[HeaderKV] = []
    header_map: dict[str, list[str]] = {}

    for raw in raw_headers or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        value = raw.get("value")
        value_str = None if value is None else str(value)
        lower_name = name.lower()
        header = HeaderKV(
            name=name,
            value=value_str,
            lower_name=lower_name,
            redacted=False,
        )
        headers.append(header)
        header_map.setdefault(lower_name, []).append(value_str or "")

    return headers, header_map, []


def build_header_highlights(
    header_map: dict[str, list[str]],
    *,
    max_items: int = 8,
) -> dict[str, str]:
    """Build a compact header preview for summary outputs."""
    highlights: "OrderedDict[str, str]" = OrderedDict()

    for key in _HIGHLIGHT_ORDER:
        values = header_map.get(key)
        if values:
            highlights[key] = values[0]
        if len(highlights) >= max_items:
            return dict(highlights)

    for key in sorted(header_map):
        if key in highlights:
            continue
        values = header_map[key]
        if values:
            highlights[key] = values[0]
        if len(highlights) >= max_items:
            break

    return dict(highlights)
