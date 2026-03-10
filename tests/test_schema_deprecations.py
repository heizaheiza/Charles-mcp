from charles_mcp.schemas.traffic import (
    BodyContent,
    HeaderKV,
    HttpMessage,
    TrafficDetail,
    TrafficSummary,
)


def test_deprecated_compatibility_fields_have_been_removed_from_json_schema() -> None:
    """Verify that previously deprecated fields no longer appear in schemas."""
    header_schema = HeaderKV.model_json_schema()
    body_schema = BodyContent.model_json_schema()
    message_schema = HttpMessage.model_json_schema()
    summary_schema = TrafficSummary.model_json_schema()
    detail_schema = TrafficDetail.model_json_schema()

    assert "redacted" not in header_schema["properties"]
    assert "redactions_applied" not in body_schema["properties"]
    assert "redactions_applied" not in message_schema["properties"]
    assert "redactions_applied" not in summary_schema["properties"]
    assert "sensitive_included" not in detail_schema["properties"]
