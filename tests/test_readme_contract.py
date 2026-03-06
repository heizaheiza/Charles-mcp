from pathlib import Path


def test_readme_documents_entrypoints_lifecycle_and_stop_recovery_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "charles_mcp.main" in readme
    assert "CHARLES_MANAGE_LIFECYCLE" in readme
    assert "start_live_capture" in readme
    assert "read_live_capture" in readme
    assert "group_capture_analysis" in readme
    assert "stop_failed" in readme
    assert "recoverable" in readme
    assert "active_capture_preserved" in readme
    assert "PowerShell" in readme
    assert "Windows CMD" in readme
    assert "Git Bash / Bash / Zsh" in readme
    assert "README.en.md" in readme
    assert "docs/contracts/tools.md" in readme
