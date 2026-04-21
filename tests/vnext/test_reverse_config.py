import json
from pathlib import Path

import charles_mcp.reverse.config as reverse_config_module
from charles_mcp.config import Config
from charles_mcp.reverse.config import build_reverse_config


def test_reverse_config_migrates_legacy_state_dir(tmp_path, monkeypatch) -> None:
    legacy_root = tmp_path / "legacy-vnext"
    legacy_root.mkdir(parents=True, exist_ok=True)
    (legacy_root / "reverse.sqlite3").write_text("legacy-db", encoding="utf-8")
    (legacy_root / "artifacts").mkdir()
    (legacy_root / "artifacts" / "note.txt").write_text("artifact", encoding="utf-8")

    new_state_root = tmp_path / "charles-state"
    monkeypatch.setenv("CHARLES_STATE_DIR", str(new_state_root))
    monkeypatch.setenv("CHARLES_VNEXT_STATE_DIR", str(legacy_root))

    reverse_config = build_reverse_config(Config())
    target_root = new_state_root / "reverse"

    assert reverse_config.state_root == target_root.resolve()
    assert reverse_config.database_path == target_root.resolve() / "reverse.sqlite3"
    assert (target_root / "reverse.sqlite3").read_text(encoding="utf-8") == "legacy-db"
    assert (target_root / "artifacts" / "note.txt").read_text(encoding="utf-8") == "artifact"
    assert not legacy_root.exists()

    marker = json.loads((target_root / ".vnext-state-migration.json").read_text(encoding="utf-8"))
    assert marker["migrated_items"] == ["*"]
    assert marker["source_root"] == str(legacy_root.resolve())


def test_reverse_config_falls_back_to_legacy_state_dir_when_migration_is_blocked(
    tmp_path,
    monkeypatch,
) -> None:
    legacy_root = tmp_path / "legacy-vnext"
    legacy_root.mkdir(parents=True, exist_ok=True)
    (legacy_root / "reverse.sqlite3").write_text("legacy-db", encoding="utf-8")
    new_state_root = tmp_path / "charles-state"

    monkeypatch.setenv("CHARLES_STATE_DIR", str(new_state_root))
    monkeypatch.setenv("CHARLES_VNEXT_STATE_DIR", str(legacy_root))

    def _blocked_move(src: str, dst: str) -> None:
        raise PermissionError(f"blocked {src} -> {dst}")

    monkeypatch.setattr(reverse_config_module.shutil, "move", _blocked_move)

    reverse_config = build_reverse_config(Config())

    assert reverse_config.state_root == legacy_root.resolve()
    assert reverse_config.database_path == legacy_root.resolve() / "reverse.sqlite3"
    assert (legacy_root / "reverse.sqlite3").read_text(encoding="utf-8") == "legacy-db"
    assert not (new_state_root / "reverse" / ".vnext-state-migration.json").exists()
