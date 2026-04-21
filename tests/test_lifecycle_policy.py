import pytest

import charles_mcp.server as server_module
from charles_mcp.config import Config
from charles_mcp.server import create_server


def test_config_disables_automatic_charles_management_by_default() -> None:
    config = Config()

    assert config.manage_charles_lifecycle is False


@pytest.mark.asyncio
async def test_public_lifespan_skips_backup_and_restore_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_restore(config):
        calls.append("restore")
        return True

    monkeypatch.setattr(server_module, "backup_config", lambda config: calls.append("backup") or True)
    monkeypatch.setattr(server_module, "restore_config", fake_restore)

    server = create_server(Config())

    async with server.settings.lifespan(server):
        pass

    assert calls == []


@pytest.mark.asyncio
async def test_public_lifespan_runs_backup_and_restore_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_restore(config):
        calls.append("restore")
        return True

    monkeypatch.setattr(server_module, "backup_config", lambda config: calls.append("backup") or True)
    monkeypatch.setattr(server_module, "restore_config", fake_restore)

    server = create_server(Config(manage_charles_lifecycle=True))

    async with server.settings.lifespan(server):
        pass

    assert calls == ["backup", "restore"]
