try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from pathlib import Path


def test_pyproject_metadata_matches_current_project_contract() -> None:
    with Path("pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)

    project = data["project"]

    assert project["readme"]["file"] == "README.en.md"
    assert project["readme"]["content-type"] == "text/markdown"
    assert "mcp>=1.25.0" in project["dependencies"]
    assert "pydantic>=2.12.0" in project["dependencies"]
    assert "jmespath>=1.0.1" in project["dependencies"]
    assert project["scripts"]["charles-mcp"] == "charles_mcp.main:main"
    assert project["urls"]["Documentation"].endswith("/docs/README.md")
    assert "README.en.md" not in project["urls"]["Documentation"]
    assert "charles-mcp-vnext" not in project["scripts"]
    assert "traffic-analysis" in project["keywords"]
