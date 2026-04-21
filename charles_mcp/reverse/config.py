"""Reverse-analysis configuration derived from the main Charles MCP config."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from charles_mcp.config import Config, get_config as get_base_config

_MIGRATION_MARKER = ".vnext-state-migration.json"


def _legacy_default_state_root() -> Path:
    user_home = Path.home()
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "charles-mcp-vnext"
        return user_home / "AppData" / "Local" / "charles-mcp-vnext"

    if sys.platform == "darwin":
        return user_home / "Library" / "Application Support" / "charles-mcp-vnext"

    xdg_state_home = os.getenv("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "charles-mcp-vnext"
    return user_home / ".local" / "state" / "charles-mcp-vnext"


def _resolve_legacy_state_root() -> Path:
    env_state_root = os.getenv("CHARLES_VNEXT_STATE_DIR")
    return Path(env_state_root) if env_state_root else _legacy_default_state_root()


def _write_migration_marker(
    *,
    state_root: Path,
    source_root: Path,
    migrated_items: list[str],
    skipped_existing: list[str],
) -> None:
    marker_path = state_root / _MIGRATION_MARKER
    payload = {
        "source_root": str(source_root),
        "migrated_items": migrated_items,
        "skipped_existing": skipped_existing,
        "migrated_at": datetime.now(timezone.utc).isoformat(),
    }
    marker_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _migrate_legacy_state_root(state_root: Path) -> Path:
    state_root = state_root.expanduser().resolve()
    legacy_root = _resolve_legacy_state_root().expanduser().resolve()
    marker_path = state_root / _MIGRATION_MARKER

    if marker_path.exists():
        state_root.mkdir(parents=True, exist_ok=True)
        return state_root

    if legacy_root == state_root or not legacy_root.exists() or not legacy_root.is_dir():
        state_root.mkdir(parents=True, exist_ok=True)
        return state_root

    state_root.parent.mkdir(parents=True, exist_ok=True)
    state_root_exists = state_root.exists()
    if not state_root_exists:
        try:
            shutil.move(str(legacy_root), str(state_root))
        except (OSError, PermissionError):
            return legacy_root
        _write_migration_marker(
            state_root=state_root,
            source_root=legacy_root,
            migrated_items=["*"],
            skipped_existing=[],
        )
        return state_root

    state_root.mkdir(parents=True, exist_ok=True)
    migrated_items: list[str] = []
    skipped_existing: list[str] = []
    blocked_items: list[str] = []
    for item in legacy_root.iterdir():
        target = state_root / item.name
        if target.exists():
            skipped_existing.append(item.name)
            continue
        try:
            shutil.move(str(item), str(target))
        except (OSError, PermissionError):
            blocked_items.append(item.name)
            continue
        migrated_items.append(item.name)

    if migrated_items or skipped_existing:
        _write_migration_marker(
            state_root=state_root,
            source_root=legacy_root,
            migrated_items=migrated_items,
            skipped_existing=skipped_existing,
        )

    try:
        next(legacy_root.iterdir())
    except StopIteration:
        legacy_root.rmdir()
    except OSError:
        pass

    if blocked_items and not migrated_items and not skipped_existing:
        return legacy_root

    return state_root


@dataclass
class VNextConfig:
    state_root: Path
    database_path: Path = field(init=False)
    artifacts_dir: Path = field(init=False)
    temp_dir: Path = field(init=False)
    charles_cli_path: str | None = None
    replay_timeout_seconds: float = 20.0
    live_session_ttl_seconds: int = 900
    live_session_snapshot_history_limit: int = 20
    max_query_limit: int = 100
    charles_user: str = "admin"
    charles_pass: str = "123456"
    charles_base_url: str = "http://control.charles"
    charles_proxy_host: str = "127.0.0.1"
    charles_proxy_port: int = 8888

    def __post_init__(self) -> None:
        self.state_root = self.state_root.expanduser().resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.database_path = self.state_root / "reverse.sqlite3"
        self.artifacts_dir = self.state_root / "artifacts"
        self.temp_dir = self.state_root / "tmp"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @property
    def charles_proxy_url(self) -> str:
        return f"http://{self.charles_proxy_host}:{self.charles_proxy_port}"


def build_reverse_config(config: Config | None = None) -> VNextConfig:
    base_config = config or get_base_config()
    state_root = _migrate_legacy_state_root(Path(base_config.reverse_state_dir))
    return VNextConfig(
        state_root=state_root,
        charles_cli_path=base_config.charles_cli_path,
        replay_timeout_seconds=base_config.reverse_replay_timeout_seconds,
        live_session_ttl_seconds=base_config.reverse_live_session_ttl_seconds,
        live_session_snapshot_history_limit=base_config.reverse_live_snapshot_history_limit,
        max_query_limit=base_config.reverse_max_query_limit,
        charles_user=base_config.charles_user,
        charles_pass=base_config.charles_pass,
        charles_base_url=base_config.charles_base_url,
        charles_proxy_host=base_config.proxy_host,
        charles_proxy_port=base_config.proxy_port,
    )


_default_config: VNextConfig | None = None


def get_config() -> VNextConfig:
    global _default_config
    if _default_config is None:
        _default_config = build_reverse_config()
    return _default_config


def reset_config() -> None:
    global _default_config
    _default_config = None
