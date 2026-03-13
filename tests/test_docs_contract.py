from pathlib import Path


def test_english_readme_documents_current_install_and_runtime_contract() -> None:
    readme = Path("README.en.md").read_text(encoding="utf-8")

    assert "Quick Start" in readme
    assert "Install and configure your MCP client" in readme
    assert "Tool Catalog" in readme
    assert "uvx" in readme
    assert "Claude Code CLI" in readme
    assert "Codex CLI" in readme
    assert "generic JSON config" in readme
    assert "Auto-install via AI agent" in readme
    assert "charles_mcp.main" in readme
    assert "admin" in readme
    assert "stop_failed" in readme
    assert "recoverable" in readme
    assert "active_capture_preserved" in readme
    assert "group_capture_analysis" in readme
    assert "PowerShell" not in readme
    assert "Antigravity" not in readme
    assert "proxy_by_time" not in readme
    assert "filter_func" not in readme
    assert "list_sessions" not in readme


def test_tool_contract_documents_agent_stop_recovery_flow() -> None:
    contract = Path("docs/contracts/tools.md").read_text(encoding="utf-8")

    assert "推荐工具范围" in contract
    assert "stop_live_capture" in contract
    assert "stop_failed" in contract
    assert "recoverable" in contract
    assert "active_capture_preserved" in contract
    assert "group_capture_analysis" in contract
    assert "query_live_capture_entries" in contract
    assert "CHARLES_MANAGE_LIFECYCLE=false" in contract
    assert "admin" in contract
    assert "README.md" in contract
    assert "README.en.md" in contract
    assert "proxy_by_time" not in contract
    assert "filter_func" not in contract
    assert "list_sessions" not in contract