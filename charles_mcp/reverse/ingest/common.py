"""Shared helpers for Charles session ingestion."""

from __future__ import annotations

import hashlib


def header_value(headers: dict[str, list[str]], name: str) -> str | None:
    values = headers.get(name.lower())
    return values[0] if values else None


def parse_cookie_header(values: list[str] | None) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for value in values or []:
        for chunk in value.split(";"):
            if "=" not in chunk:
                continue
            name, cookie_value = chunk.split("=", 1)
            cookies[name.strip()] = cookie_value.strip()
    return cookies


def parse_set_cookie_headers(values: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            continue
        name, cookie_value = value.split("=", 1)
        result[name.strip()] = cookie_value.split(";", 1)[0].strip()
    return result


def hash_headers(headers: dict[str, list[str]]) -> str | None:
    if not headers:
        return None
    payload = "\n".join(
        f"{name}:{'|'.join(values)}"
        for name, values in sorted(headers.items())
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def reason_phrase(first_line: str | None) -> str | None:
    if not first_line:
        return None
    parts = first_line.split(" ", 2)
    if len(parts) < 3:
        return None
    return parts[2]


def build_body_blob_id(capture_id: str, sequence_no: int, side: str) -> str:
    return hashlib.sha1(f"{capture_id}|{sequence_no}|{side}".encode("utf-8")).hexdigest()
