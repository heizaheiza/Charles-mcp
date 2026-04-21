from pathlib import Path

from charles_mcp.tools.public_surface import LEGACY_COMPAT_TOOL_NAMES


def test_legacy_migration_doc_covers_all_compatibility_tools() -> None:
    content = Path("docs/migrations/legacy-tools.md").read_text(encoding="utf-8").lower()

    for tool_name in LEGACY_COMPAT_TOOL_NAMES:
        assert f"`{tool_name}`" in content


def test_legacy_migration_doc_has_explicit_status_and_replacement_guidance() -> None:
    content = Path("docs/migrations/legacy-tools.md").read_text(encoding="utf-8").lower()

    assert "deprecated compatibility alias" in content
    assert "no direct replacement" in content
    assert "tbd" not in content
    assert "待补充" not in content

    # Explicitly verify the documented no-direct-replacement decision for proxy_by_time.
    assert "`proxy_by_time`" in content
    assert "no direct replacement" in content
