"""Classify traffic entries before deeper normalization."""

from __future__ import annotations

import os

from charles_mcp.schemas.traffic import ResourceClassification

_STATIC_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".css",
    ".map",
}
_FONT_EXTENSIONS = {".woff", ".woff2", ".ttf", ".eot", ".otf"}
_MEDIA_EXTENSIONS = {".mp3", ".mp4", ".wav", ".webm", ".mov", ".avi", ".m4a"}
_SCRIPT_EXTENSIONS = {".js", ".mjs"}
_API_HINTS = ("/api/", "/graphql", "/rpc", "/auth", "/login", "/token", "/session")


def classify_entry(entry: dict) -> ResourceClassification:
    """Assign a coarse resource class and priority score."""
    host = str(entry.get("host") or "").lower()
    method = str(entry.get("method") or "").upper()
    path = str(entry.get("path") or "")
    response = entry.get("response") or {}
    request = entry.get("request") or {}
    status = response.get("status")
    response_mime = str(response.get("mimeType") or "").lower()
    request_mime = str(request.get("mimeType") or "").lower()
    extension = os.path.splitext(path.lower())[1]

    if host == "control.charles":
        return ResourceClassification(resource_class="control", priority_score=0)

    if method == "CONNECT":
        return ResourceClassification(resource_class="connect_tunnel", priority_score=0)

    if response_mime.startswith("image/") or extension in _STATIC_EXTENSIONS:
        return ResourceClassification(resource_class="static_asset", priority_score=5)

    if response_mime.startswith("font/") or extension in _FONT_EXTENSIONS:
        return ResourceClassification(resource_class="font", priority_score=5)

    if response_mime.startswith("audio/") or response_mime.startswith("video/") or extension in _MEDIA_EXTENSIONS:
        return ResourceClassification(resource_class="media", priority_score=5)

    if "text/html" in response_mime:
        return ResourceClassification(resource_class="document", priority_score=40)

    if (
        "javascript" in response_mime
        or "ecmascript" in response_mime
        or extension in _SCRIPT_EXTENSIONS
    ):
        return ResourceClassification(resource_class="script", priority_score=35)

    reasons: list[str] = []
    score = 20
    lower_path = path.lower()

    if "application/json" in response_mime or "application/json" in request_mime:
        score += 40
        reasons.append("json_content_type")

    if any(hint in lower_path for hint in _API_HINTS):
        score += 25
        reasons.append("api_path_hint")

    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        score += 15
        reasons.append("mutating_method")

    if isinstance(status, int) and status >= 400:
        score += 20
        reasons.append("error_status")

    if reasons:
        return ResourceClassification(
            resource_class="api_candidate",
            priority_score=score,
            priority_reasons=reasons,
        )

    return ResourceClassification(resource_class="unknown", priority_score=20)
