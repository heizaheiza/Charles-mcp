from pathlib import Path


def test_docs_hub_and_related_contract_docs_exist() -> None:
    assert Path("docs/README.md").exists()
    assert Path("AGENTS.md").exists()
    assert Path("docs/agent-workflows.md").exists()
    assert Path("docs/contracts/tools.md").exists()
    assert Path("docs/migrations/legacy-tools.md").exists()


def test_docs_hub_links_and_responsibilities_are_declared() -> None:
    hub = Path("docs/README.md").read_text(encoding="utf-8")

    assert "../README.md" in hub
    assert "../README.en.md" in hub
    assert "../AGENTS.md" in hub
    assert "./agent-workflows.md" in hub
    assert "./contracts/tools.md" in hub
    assert "./migrations/legacy-tools.md" in hub
    assert "global agent behavior rules" in hub
    assert "task-oriented workflow playbooks" in hub
    assert "canonical public tool surface" in hub


def test_readme_navigation_includes_docs_and_agent_contract_entrypoints() -> None:
    readme_zh = Path("README.md").read_text(encoding="utf-8")
    readme_en = Path("README.en.md").read_text(encoding="utf-8")

    for content in (readme_zh, readme_en):
        assert "docs/README.md" in content
        assert "AGENTS.md" in content
        assert "docs/agent-workflows.md" in content
        assert "docs/contracts/tools.md" in content
