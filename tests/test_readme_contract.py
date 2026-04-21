from pathlib import Path


def test_readme_documents_current_install_and_runtime_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "快速开始" in readme
    assert "安装并配置到 MCP 客户端" in readme
    assert "工具总览" in readme
    assert "uvx" in readme
    assert "Claude Code CLI" in readme
    assert "Codex CLI" in readme
    assert "通用 JSON 配置" in readme
    assert "让 AI 自动安装" in readme
    assert "charles_mcp.main" in readme
    assert "CHARLES_MANAGE_LIFECYCLE" in readme
    assert "CHARLES_USER" in readme
    assert "admin" in readme
    assert "start_live_capture" in readme
    assert "read_live_capture" in readme
    assert "group_capture_analysis" in readme
    assert "reverse_start_live_analysis" in readme
    assert "reverse_import_session" in readme
    assert "stop_failed" in readme
    assert "recoverable" in readme
    assert "active_capture_preserved" in readme
    assert "README.en.md" in readme
    assert "docs/README.md" in readme
    assert "docs/contracts/tools.md" in readme
    assert "AGENTS.md" in readme
    assert "docs/agent-workflows.md" in readme
    assert "PowerShell" not in readme
    assert "Windows CMD" not in readme
    assert "Git Bash / Bash / Zsh" not in readme
    assert "Antigravity" not in readme
    assert "legacy aliases" in readme.lower() or "兼容层" in readme
