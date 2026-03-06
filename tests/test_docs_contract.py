from pathlib import Path


def test_english_readme_documents_stop_recovery_and_entrypoint() -> None:
    readme = Path("README.en.md").read_text(encoding="utf-8")

    assert "charles_mcp.main" in readme
    assert "admin" in readme
    assert "stop_failed" in readme
    assert "recoverable" in readme
    assert "active_capture_preserved" in readme
    assert "group_capture_analysis" in readme
    assert "PowerShell" in readme
    assert "Claude CLI" in readme
    assert "Codex CLI" in readme
    assert "Antigravity" in readme


def test_tool_contract_documents_agent_stop_recovery_flow() -> None:
    contract = Path("docs/contracts/tools.md").read_text(encoding="utf-8")

    assert "stop_live_capture" in contract
    assert "stop_failed" in contract
    assert "recoverable" in contract
    assert "active_capture_preserved" in contract
    assert "group_capture_analysis" in contract
    assert "query_live_capture_entries" in contract
    assert "CHARLES_MANAGE_LIFECYCLE=false" in contract
    assert "admin" in contract
    assert "Claude CLI" in contract
    assert "Codex CLI" in contract
    assert "Antigravity" in contract
