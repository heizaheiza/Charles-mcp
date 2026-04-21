from charles_mcp.reverse.ingest import SessionSource, probe_session_source
from charles_mcp.reverse.models import CaptureSourceFormat


def test_probe_session_source_accepts_xml_and_native_suffixes(tmp_path):
    xml_path = tmp_path / "capture.xml"
    xml_path.write_text("<session />", encoding="utf-8")
    native_path = tmp_path / "capture.chls"
    native_path.write_bytes(b"charles-native")

    xml_probe = probe_session_source(
        SessionSource(source_format=CaptureSourceFormat.XML, path=str(xml_path))
    )
    native_probe = probe_session_source(
        SessionSource(source_format=CaptureSourceFormat.NATIVE, path=str(native_path))
    )

    assert xml_probe.supported is True
    assert native_probe.supported is True


def test_probe_session_source_flags_legacy_and_unexpected_suffix(tmp_path):
    legacy_path = tmp_path / "capture.chlsj"
    legacy_path.write_text("[]", encoding="utf-8")
    wrong_path = tmp_path / "capture.txt"
    wrong_path.write_text("payload", encoding="utf-8")

    legacy_probe = probe_session_source(
        SessionSource(source_format=CaptureSourceFormat.LEGACY_JSON, path=str(legacy_path))
    )
    wrong_probe = probe_session_source(
        SessionSource(source_format=CaptureSourceFormat.XML, path=str(wrong_path))
    )

    assert "legacy_data_plane_only_for_compatibility" in legacy_probe.warnings
    assert wrong_probe.supported is False
    assert any(item.startswith("unexpected_suffix") for item in wrong_probe.warnings)

