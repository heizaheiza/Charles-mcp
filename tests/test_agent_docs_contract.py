from pathlib import Path


def test_agent_docs_exist() -> None:
    assert Path("AGENTS.md").exists()
    assert Path("docs/agent-workflows.md").exists()


def test_agents_doc_contains_core_sections_and_semantics() -> None:
    content = Path("AGENTS.md").read_text(encoding="utf-8").lower()

    assert "summary first, detail on demand" in content
    assert "global operating model" in content
    assert "identity and plane rules" in content
    assert "read vs peek semantics" in content
    assert "reverse workflow usage principles" in content
    assert "docs/agent-workflows.md" in content
    assert "stop_live_capture" in content
    assert "stop_failed" in content


def test_agent_workflows_doc_contains_core_sections_and_semantics() -> None:
    content = Path("docs/agent-workflows.md").read_text(encoding="utf-8").lower()

    assert "workflow a" in content
    assert "workflow b" in content
    assert "workflow c" in content
    assert "workflow d" in content
    assert "workflow selection cheatsheet" in content
    assert "response policy for agents" in content
    assert "summary before detail" in content
    assert "final rule" in content
