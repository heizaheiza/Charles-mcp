import tomllib
from pathlib import Path


def test_pyproject_console_script_points_to_package_main() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    scripts = pyproject["project"]["scripts"]

    assert scripts["charles-mcp"] == "charles_mcp.main:main"


def test_package_main_runs_server_with_stdio(monkeypatch) -> None:
    from charles_mcp import main as main_module

    calls: list[object] = []

    class FakeServer:
        def run(self, *, transport: str) -> None:
            calls.append(("run", transport))

    monkeypatch.setattr(main_module, "setup_logging", lambda **kwargs: calls.append(("logging", kwargs)))
    monkeypatch.setattr(main_module, "setup_windows_stdio", lambda: calls.append(("stdio", None)))
    monkeypatch.setattr(main_module, "create_server", lambda: FakeServer())

    main_module.main()

    assert ("run", "stdio") in calls


def test_package_main_respects_charles_log_dir(monkeypatch, tmp_path) -> None:
    from charles_mcp import main as main_module

    calls: list[object] = []

    class FakeServer:
        def run(self, *, transport: str) -> None:
            calls.append(("run", transport))

    log_dir = tmp_path / "logs"
    monkeypatch.setenv("CHARLES_LOG_DIR", str(log_dir))
    monkeypatch.setattr(main_module, "setup_logging", lambda **kwargs: calls.append(("logging", kwargs)))
    monkeypatch.setattr(main_module, "setup_windows_stdio", lambda: calls.append(("stdio", None)))
    monkeypatch.setattr(main_module, "create_server", lambda: FakeServer())

    main_module.main()

    assert ("run", "stdio") in calls
    assert any(
        call[0] == "logging" and call[1]["log_file"] == str(log_dir / "debug.log")
        for call in calls
    )