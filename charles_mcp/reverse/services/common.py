"""Common helpers shared by vnext reverse-analysis services."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlunsplit
from uuid import uuid4


def new_identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_entry_url(
    *,
    scheme: str | None,
    host: str,
    path: str,
    query: str | None,
    port: int | None = None,
) -> str:
    normalized_path = path or "/"
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    netloc = host
    if port and not _is_default_port(scheme or "http", port):
        netloc = f"{host}:{port}"
    return urlunsplit((scheme or "http", netloc, normalized_path, query or "", ""))


def parse_request_parameters(
    *,
    query: str | None,
    request_content_type: str | None,
    request_text: str | None,
) -> dict[str, list[str]]:
    params: dict[str, list[str]] = {}
    for name, values in parse_qs(query or "", keep_blank_values=True).items():
        params[f"query.{name}"] = values

    lower_content_type = (request_content_type or "").lower()
    if request_text:
        if "application/json" in lower_content_type:
            try:
                payload = json.loads(request_text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                _flatten_json("json", payload, params)
        elif "application/x-www-form-urlencoded" in lower_content_type:
            for name, values in parse_qs(request_text, keep_blank_values=True).items():
                params[f"form.{name}"] = values
    return params


def apply_query_overrides(query: str | None, overrides: dict[str, Any] | None) -> str | None:
    if not overrides:
        return query

    current = parse_qs(query or "", keep_blank_values=True)
    for key, value in overrides.items():
        if value is None:
            current.pop(key, None)
            continue
        if isinstance(value, list):
            current[key] = [str(item) for item in value]
        else:
            current[key] = [str(value)]
    return urlencode(current, doseq=True)


def hash_payload(value: bytes | str) -> str:
    payload = value if isinstance(value, bytes) else value.encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()


def _flatten_json(prefix: str, payload: dict[str, Any], target: dict[str, list[str]]) -> None:
    for key, value in payload.items():
        path = f"{prefix}.{key}"
        if isinstance(value, dict):
            _flatten_json(path, value, target)
        elif isinstance(value, list):
            target[path] = [json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item) for item in value]
        else:
            target[path] = [str(value)]


def ensure_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)


def _is_default_port(scheme: str, port: int) -> bool:
    if scheme == "http" and port == 80:
        return True
    if scheme == "https" and port == 443:
        return True
    return False
