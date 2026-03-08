import base64

from charles_mcp.analyzers.resource_classifier import classify_entry
from charles_mcp.config import Config
from charles_mcp.services.traffic_normalizer import TrafficNormalizer


def _api_entry() -> dict:
    return {
        "status": "COMPLETE",
        "method": "POST",
        "scheme": "https",
        "host": "api.example.com",
        "path": "/api/login",
        "query": "device=ios",
        "times": {"start": "2026-03-06T10:00:00.000+08:00"},
        "durations": {"total": 20},
        "totalSize": 1024,
        "request": {
            "mimeType": "application/json",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": 64},
            "header": {
                "firstLine": "POST /api/login HTTP/1.1",
                "headers": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Authorization", "value": "Bearer secret-token"},
                ],
            },
            "body": {
                "text": '{"username":"alice","password":"secret-password","token":"abc"}',
            },
        },
        "response": {
            "status": 200,
            "mimeType": "application/json",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": 120},
            "header": {
                "firstLine": "HTTP/1.1 200 OK",
                "headers": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Set-Cookie", "value": "sessionid=super-secret"},
                ],
            },
            "body": {
                "text": '{"ok":true,"access_token":"top-secret","user":{"id":1}}',
            },
        },
    }


def _image_entry() -> dict:
    return {
        "status": "COMPLETE",
        "method": "GET",
        "scheme": "https",
        "host": "static.example.com",
        "path": "/assets/logo.png",
        "query": None,
        "times": {"start": "2026-03-06T10:00:01.000+08:00"},
        "durations": {"total": 8},
        "totalSize": 24576,
        "request": {
            "mimeType": None,
            "charset": None,
            "contentEncoding": None,
            "sizes": {"body": 0},
            "header": {"firstLine": "GET /assets/logo.png HTTP/1.1", "headers": []},
        },
        "response": {
            "status": 200,
            "mimeType": "image/png",
            "charset": None,
            "contentEncoding": None,
            "sizes": {"body": 24576},
            "header": {
                "firstLine": "HTTP/1.1 200 OK",
                "headers": [{"name": "Content-Type", "value": "image/png"}],
            },
        },
    }


def _multipart_entry() -> dict:
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="meta"\r\n'
        "Content-Type: application/json\r\n\r\n"
        '{"title":"hello","token":"super-token"}\r\n'
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="report.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "report body\r\n"
        f"--{boundary}--\r\n"
    )
    return {
        "status": "COMPLETE",
        "method": "POST",
        "scheme": "https",
        "host": "upload.example.com",
        "path": "/api/upload",
        "query": None,
        "times": {"start": "2026-03-06T10:00:02.000+08:00"},
        "durations": {"total": 42},
        "totalSize": 4096,
        "request": {
            "mimeType": f"multipart/form-data; boundary={boundary}",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": len(body)},
            "header": {
                "firstLine": "POST /api/upload HTTP/1.1",
                "headers": [
                    {
                        "name": "Content-Type",
                        "value": f"multipart/form-data; boundary={boundary}",
                    }
                ],
            },
            "body": {"text": body},
        },
        "response": {
            "status": 201,
            "mimeType": "application/json",
            "charset": "utf-8",
            "contentEncoding": None,
            "sizes": {"body": 32},
            "header": {
                "firstLine": "HTTP/1.1 201 Created",
                "headers": [{"name": "Content-Type", "value": "application/json"}],
            },
            "body": {"text": '{"ok":true}'},
        },
    }


def test_resource_classifier_prioritizes_api_and_filters_image_assets() -> None:
    api = classify_entry(_api_entry())
    image = classify_entry(_image_entry())

    assert api.resource_class == "api_candidate"
    assert api.priority_score > image.priority_score
    assert image.resource_class == "static_asset"


def test_traffic_normalizer_redacts_sensitive_headers_and_body_fields() -> None:
    normalizer = TrafficNormalizer(Config())

    entry = normalizer.normalize_entry(
        _api_entry(),
        capture_source="history",
        recording_path="package/example.chlsj",
        include_sensitive=False,
        include_full_body=False,
        max_preview_chars=80,
        max_headers_per_side=8,
    )

    assert entry.request.header_map["authorization"] == ["Bearer secret-token"]
    assert entry.response.header_map["set-cookie"] == ["sessionid=super-secret"]
    assert "secret-password" in (entry.request.body.preview_text or "")
    assert "top-secret" in (entry.response.body.preview_text or "")
    assert entry.request.body.kind == "json"
    assert entry.response.body.kind == "json"
    assert entry.request.body.model_dump()["redactions_applied"] == []
    assert entry.response.body.model_dump()["redactions_applied"] == []


def test_traffic_normalizer_ignores_include_sensitive_flag() -> None:
    normalizer = TrafficNormalizer(Config())

    default_entry = normalizer.normalize_entry(
        _api_entry(),
        capture_source="history",
        recording_path="package/example.chlsj",
        include_sensitive=False,
        include_full_body=False,
        max_preview_chars=80,
        max_headers_per_side=8,
    )
    explicit_entry = normalizer.normalize_entry(
        _api_entry(),
        capture_source="history",
        recording_path="package/example.chlsj",
        include_sensitive=True,
        include_full_body=False,
        max_preview_chars=80,
        max_headers_per_side=8,
    )

    assert default_entry.model_dump() == explicit_entry.model_dump()


def test_traffic_normalizer_summarizes_multipart_parts() -> None:
    normalizer = TrafficNormalizer(Config())

    entry = normalizer.normalize_entry(
        _multipart_entry(),
        capture_source="history",
        recording_path="package/upload.chlsj",
        include_sensitive=False,
        include_full_body=True,
        max_preview_chars=120,
        max_headers_per_side=8,
    )

    assert entry.request.body.kind == "multipart"
    assert len(entry.request.body.multipart_summary) == 2
    assert entry.request.body.multipart_summary[0]["name"] == "meta"
    assert entry.request.body.multipart_summary[0]["content_type"] == "application/json"
    assert entry.request.body.multipart_summary[1]["filename"] == "report.txt"
    assert "multipart/form-data with 2 part(s)" in (entry.request.body.preview_text or "")


def test_traffic_normalizer_decodes_encoded_multipart_parts() -> None:
    normalizer = TrafficNormalizer(Config())
    raw_entry = _multipart_entry()
    raw_text = raw_entry["request"]["body"]["text"]
    raw_entry["request"]["body"] = {
        "encoded": True,
        "text": base64.b64encode(raw_text.encode("utf-8")).decode("ascii"),
    }

    entry = normalizer.normalize_entry(
        raw_entry,
        capture_source="history",
        recording_path="package/upload-encoded.chlsj",
        include_sensitive=False,
        include_full_body=False,
        max_preview_chars=120,
        max_headers_per_side=8,
    )

    assert entry.request.body.kind == "multipart"
    assert len(entry.request.body.multipart_summary) == 2


def test_traffic_normalizer_uses_header_boundary_when_mimetype_is_generic() -> None:
    normalizer = TrafficNormalizer(Config())
    raw_entry = _multipart_entry()
    raw_entry["request"]["mimeType"] = "multipart/form-data"

    entry = normalizer.normalize_entry(
        raw_entry,
        capture_source="history",
        recording_path="package/upload-header-boundary.chlsj",
        include_sensitive=False,
        include_full_body=False,
        max_preview_chars=120,
        max_headers_per_side=8,
    )

    assert entry.request.body.kind == "multipart"
    assert len(entry.request.body.multipart_summary) == 2
