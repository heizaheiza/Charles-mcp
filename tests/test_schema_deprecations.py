from charles_mcp.schemas.traffic import (
    BodyContent,
    HeaderKV,
    HttpMessage,
    TrafficDetail,
    TrafficSummary,
)
from charles_mcp.schemas.traffic_query import TrafficQuery


def test_compatibility_fields_are_marked_deprecated_in_json_schema() -> None:
    header_schema = HeaderKV.model_json_schema()
    body_schema = BodyContent.model_json_schema()
    message_schema = HttpMessage.model_json_schema()
    summary_schema = TrafficSummary.model_json_schema()
    detail_schema = TrafficDetail.model_json_schema()
    query_schema = TrafficQuery.model_json_schema()

    assert header_schema["properties"]["redacted"]["deprecated"] is True
    assert body_schema["properties"]["redactions_applied"]["deprecated"] is True
    assert message_schema["properties"]["redactions_applied"]["deprecated"] is True
    assert summary_schema["properties"]["redactions_applied"]["deprecated"] is True
    assert detail_schema["properties"]["sensitive_included"]["deprecated"] is True
    assert query_schema["properties"]["include_sensitive"]["deprecated"] is True
