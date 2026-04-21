import base64
import gzip
import json

import brotli
import pytest
import zstandard
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from charles_mcp.reverse.config import VNextConfig
from charles_mcp.reverse.models import CaptureSourceFormat, CaptureSourceKind
from charles_mcp.reverse.services import DecodeService, IngestService
from charles_mcp.reverse.storage import SQLiteStore


def _make_single_transaction_xml(*, content_type: str, body_text: str, body_encoding: str = "plain", content_encoding: str | None = None) -> str:
    response_headers = [
        "<header><name>Content-Type</name><value>{}</value></header>".format(content_type)
    ]
    if content_encoding:
        response_headers.append(
            "<header><name>Content-Encoding</name><value>{}</value></header>".format(content_encoding)
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<charles-session>
  <transaction method="GET" protocolVersion="HTTP/1.1" protocol="https" host="api.example.com" port="443" actualPort="443" path="/payload" query="" remoteAddress="1.1.1.1" clientAddress="127.0.0.1" startTime="2026-04-13T12:00:00Z" startTimeMillis="1713000000000" responseTime="2026-04-13T12:00:01Z" responseTimeMillis="1713000001000" endTime="2026-04-13T12:00:01Z" endTimeMillis="1713000001000">
    <request headers="true" body="false">
      <headers><first-line>GET /payload HTTP/1.1</first-line></headers>
    </request>
    <response status="200" headers="true" body="true" mime-type="{content_type}">
      <headers>
        <first-line>HTTP/1.1 200 OK</first-line>
        {''.join(response_headers)}
      </headers>
      <body encoding="{body_encoding}">{body_text}</body>
    </response>
  </transaction>
</charles-session>
"""


@pytest.mark.parametrize(
    ("encoding", "payload"),
    [
        ("gzip", gzip.compress(b"hello gzip")),
        ("br", brotli.compress(b"hello brotli")),
        ("zstd", zstandard.ZstdCompressor().compress(b"hello zstd")),
    ],
)
def test_decode_service_handles_compressed_text_formats(tmp_path, encoding, payload):
    xml_path = tmp_path / f"{encoding}.xml"
    xml_path.write_text(
        _make_single_transaction_xml(
            content_type="text/plain",
            body_text=base64.b64encode(payload).decode("ascii"),
            body_encoding="base64",
            content_encoding=encoding,
        ),
        encoding="utf-8",
    )

    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    decode_service = DecodeService(store)

    imported = ingest_service.import_session(
        path=str(xml_path),
        source_format=CaptureSourceFormat.XML,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )
    entry = store.list_entries(capture_id=imported["capture_id"], limit=1)[0]
    artifact = decode_service.decode_entry_body(entry_id=entry.entry_id, side="response")

    assert artifact["artifact_type"] == "plain_text"
    assert artifact["preview_text"].startswith("hello ")


@pytest.mark.parametrize("encoding", ["gzip", "br", "zstd"])
def test_decode_service_tolerates_already_decoded_payload_with_encoding_header(tmp_path, encoding):
    xml_path = tmp_path / f"{encoding}-already-decoded.xml"
    xml_path.write_text(
        _make_single_transaction_xml(
            content_type="text/plain",
            body_text=f"already decoded {encoding}",
            body_encoding="plain",
            content_encoding=encoding,
        ),
        encoding="utf-8",
    )

    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    decode_service = DecodeService(store)

    imported = ingest_service.import_session(
        path=str(xml_path),
        source_format=CaptureSourceFormat.XML,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )
    entry = store.list_entries(capture_id=imported["capture_id"], limit=1)[0]
    artifact = decode_service.decode_entry_body(entry_id=entry.entry_id, side="response")

    assert artifact["artifact_type"] == "plain_text"
    assert artifact["preview_text"] == f"already decoded {encoding}"
    assert artifact["warnings"]


def test_decode_service_handles_protobuf_with_descriptor(tmp_path):
    descriptor_path = tmp_path / "login.desc"
    file_set = descriptor_pb2.FileDescriptorSet()
    file_proto = file_set.file.add()
    file_proto.name = "login.proto"
    file_proto.package = "reverse"
    message_proto = file_proto.message_type.add()
    message_proto.name = "LoginReply"
    field_proto = message_proto.field.add()
    field_proto.name = "token"
    field_proto.number = 1
    field_proto.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    field_proto.type = descriptor_pb2.FieldDescriptorProto.TYPE_STRING
    descriptor_path.write_bytes(file_set.SerializeToString())

    pool = descriptor_pool.DescriptorPool()
    for item in file_set.file:
        pool.Add(item)
    descriptor = pool.FindMessageTypeByName("reverse.LoginReply")
    message_cls = message_factory.GetMessageClass(descriptor)
    message = message_cls(token="abc")
    payload = message.SerializeToString()

    xml_path = tmp_path / "proto.xml"
    xml_path.write_text(
        _make_single_transaction_xml(
            content_type="application/x-protobuf",
            body_text=base64.b64encode(payload).decode("ascii"),
            body_encoding="base64",
        ),
        encoding="utf-8",
    )

    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    decode_service = DecodeService(store)

    imported = ingest_service.import_session(
        path=str(xml_path),
        source_format=CaptureSourceFormat.XML,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )
    entry = store.list_entries(capture_id=imported["capture_id"], limit=1)[0]
    artifact = decode_service.decode_entry_body(
        entry_id=entry.entry_id,
        side="response",
        descriptor_path=str(descriptor_path),
        message_type="reverse.LoginReply",
    )

    assert artifact["artifact_type"] == "protobuf"
    assert artifact["structured_json"]["token"] == "abc"


def test_decode_service_downgrades_invalid_json_payload_to_plain_text(tmp_path):
    xml_path = tmp_path / "invalid-json.xml"
    xml_path.write_text(
        _make_single_transaction_xml(
            content_type="application/json",
            body_text='{"broken": ',
            body_encoding="plain",
        ),
        encoding="utf-8",
    )

    config = VNextConfig(state_root=tmp_path / "state")
    store = SQLiteStore(config.database_path)
    ingest_service = IngestService(config, store)
    decode_service = DecodeService(store)

    imported = ingest_service.import_session(
        path=str(xml_path),
        source_format=CaptureSourceFormat.XML,
        source_kind=CaptureSourceKind.HISTORY_IMPORT,
    )
    entry = store.list_entries(capture_id=imported["capture_id"], limit=1)[0]
    artifact = decode_service.decode_entry_body(entry_id=entry.entry_id, side="response")

    assert artifact["artifact_type"] == "plain_text"
    assert artifact["preview_text"] == '{"broken": '
    assert "json_decode_failed" in artifact["warnings"]

