"""Configuration management for the Charles MCP server."""

from __future__ import annotations

import glob
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _default_base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _looks_like_repo_root(path: str) -> bool:
    root = Path(path)
    return (root / "pyproject.toml").exists() and (root / "charles_mcp").is_dir()


def _default_state_dir() -> str:
    env_state_dir = os.getenv("CHARLES_STATE_DIR")
    if env_state_dir:
        return env_state_dir

    user_home = Path.home()
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return os.path.join(local_app_data, "charles-mcp")
        return str(user_home / "AppData" / "Local" / "charles-mcp")

    if sys.platform == "darwin":
        return str(user_home / "Library" / "Application Support" / "charles-mcp")

    xdg_state_home = os.getenv("XDG_STATE_HOME")
    if xdg_state_home:
        return os.path.join(xdg_state_home, "charles-mcp")
    return str(user_home / ".local" / "state" / "charles-mcp")


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable with a conservative default."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, legacy_name: str | None = None) -> int:
    """Read an integer environment variable with optional legacy fallback."""
    value = os.getenv(name)
    if value is None and legacy_name:
        value = os.getenv(legacy_name)
    return int(value) if value is not None else default


def _env_float(name: str, default: float, *, legacy_name: str | None = None) -> float:
    """Read a float environment variable with optional legacy fallback."""
    value = os.getenv(name)
    if value is None and legacy_name:
        value = os.getenv(legacy_name)
    return float(value) if value is not None else default


def _detect_charles_cli_path() -> str | None:
    """Detect a local Charles executable for native export conversion."""
    env_cli = os.getenv("CHARLES_CLI_PATH")
    candidates: list[Path] = [Path(env_cli)] if env_cli else []

    if sys.platform == "win32":
        candidates.extend(
            [
                Path("C:/Program Files/Charles/Charles.exe"),
                Path("C:/Program Files (x86)/Charles/Charles.exe"),
            ]
        )
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/Charles.app/Contents/MacOS/Charles"))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


@dataclass
class Config:
    """Runtime configuration for the Charles MCP server."""

    charles_user: str = field(default_factory=lambda: os.getenv("CHARLES_USER", "admin"))
    charles_pass: str = field(default_factory=lambda: os.getenv("CHARLES_PASS", "123456"))

    proxy_host: str = field(default_factory=lambda: os.getenv("CHARLES_PROXY_HOST", "127.0.0.1"))
    proxy_port: int = field(default_factory=lambda: int(os.getenv("CHARLES_PROXY_PORT", "8888")))

    charles_base_url: str = "http://control.charles"
    charles_cli_path: Optional[str] = field(default_factory=_detect_charles_cli_path)

    config_path: Optional[str] = None
    profiles_dir: Optional[str] = None
    base_dir: str = field(default_factory=_default_base_dir)
    state_dir: str = ""
    package_dir: str = ""
    backup_dir: str = ""

    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("CHARLES_REQUEST_TIMEOUT", "10"))
    )
    max_stoptime: int = field(
        default_factory=lambda: int(os.getenv("CHARLES_MAX_STOPTIME", "3600"))
    )
    manage_charles_lifecycle: bool = field(
        default_factory=lambda: _env_bool("CHARLES_MANAGE_LIFECYCLE", False)
    )
    expose_legacy_tools: bool = field(
        default_factory=lambda: _env_bool("CHARLES_EXPOSE_LEGACY_TOOLS", False)
    )
    reverse_replay_timeout_seconds: float = field(
        default_factory=lambda: _env_float(
            "CHARLES_REVERSE_REPLAY_TIMEOUT",
            20.0,
            legacy_name="CHARLES_VNEXT_REPLAY_TIMEOUT",
        )
    )
    reverse_live_session_ttl_seconds: int = field(
        default_factory=lambda: _env_int(
            "CHARLES_REVERSE_LIVE_SESSION_TTL_SECONDS",
            900,
            legacy_name="CHARLES_VNEXT_LIVE_SESSION_TTL_SECONDS",
        )
    )
    reverse_live_snapshot_history_limit: int = field(
        default_factory=lambda: _env_int(
            "CHARLES_REVERSE_LIVE_SNAPSHOT_HISTORY_LIMIT",
            20,
            legacy_name="CHARLES_VNEXT_LIVE_SNAPSHOT_HISTORY_LIMIT",
        )
    )
    reverse_max_query_limit: int = field(
        default_factory=lambda: _env_int(
            "CHARLES_REVERSE_MAX_QUERY_LIMIT",
            100,
            legacy_name="CHARLES_VNEXT_MAX_QUERY_LIMIT",
        )
    )

    def __post_init__(self) -> None:
        if not self.state_dir:
            self.state_dir = _default_state_dir()

        source_root = Path(_default_base_dir()).resolve()
        configured_base_dir = Path(self.base_dir).resolve()
        explicit_base_dir = configured_base_dir != source_root
        prefer_base_dir = explicit_base_dir or _looks_like_repo_root(str(configured_base_dir))
        state_dir = Path(self.state_dir)

        env_package_dir = os.getenv("CHARLES_PACKAGE_DIR")
        env_backup_dir = os.getenv("CHARLES_BACKUP_DIR")

        if env_package_dir:
            self.package_dir = env_package_dir
        elif not self.package_dir:
            target_root = configured_base_dir if prefer_base_dir else state_dir
            self.package_dir = str(target_root / "package")

        if env_backup_dir:
            self.backup_dir = env_backup_dir
        elif not self.backup_dir:
            target_root = configured_base_dir if prefer_base_dir else state_dir
            self.backup_dir = str(target_root / "back")

        env_config_path = os.getenv("CHARLES_CONFIG_PATH")
        if env_config_path and os.path.exists(env_config_path):
            self.config_path = env_config_path
        else:
            self.config_path = self._detect_charles_config_path()

        if self.config_path:
            self.profiles_dir = os.path.join(os.path.dirname(self.config_path), "data", "profiles")

    @property
    def proxy_url(self) -> str:
        return f"http://{self.proxy_host}:{self.proxy_port}"

    @property
    def proxies(self) -> dict[str, str]:
        return {
            "http://": self.proxy_url,
            "https://": self.proxy_url,
        }

    @property
    def auth(self) -> tuple[str, str]:
        return (self.charles_user, self.charles_pass)

    @property
    def reverse_state_dir(self) -> str:
        env_state_dir = os.getenv("CHARLES_REVERSE_STATE_DIR")
        if env_state_dir:
            return env_state_dir
        return str(Path(self.state_dir) / "reverse")

    @classmethod
    def from_env(cls) -> "Config":
        return cls()

    def _detect_charles_config_path(self) -> Optional[str]:
        possible_patterns: list[str] = []

        if sys.platform == "win32":
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            if local_app_data:
                possible_patterns.append(
                    os.path.join(
                        local_app_data,
                        "Packages",
                        "XK72.Charles_*",
                        "RoamingState",
                        "charles.config",
                    )
                )

            app_data = os.environ.get("APPDATA", "")
            if app_data:
                possible_patterns.append(os.path.join(app_data, "Charles", "charles.config"))

            user_home = Path.home()
            possible_patterns.append(str(user_home / ".charles.config"))

        elif sys.platform == "darwin":
            user_home = Path.home()
            possible_patterns.extend(
                [
                    str(
                        user_home
                        / "Library"
                        / "Application Support"
                        / "Charles"
                        / "charles.config"
                    ),
                    str(user_home / ".charles.config"),
                ]
            )

        else:
            user_home = Path.home()
            xdg_config = os.environ.get("XDG_CONFIG_HOME", str(user_home / ".config"))
            possible_patterns.extend(
                [
                    os.path.join(xdg_config, "Charles", "charles.config"),
                    str(user_home / ".charles.config"),
                    str(user_home / ".charles" / "charles.config"),
                ]
            )

        for pattern in possible_patterns:
            if "*" in pattern:
                matches = glob.glob(pattern)
                if matches:
                    config_path = matches[0]
                    logger.info("Detected Charles config file: %s", config_path)
                    return config_path
            elif os.path.exists(pattern):
                logger.info("Found Charles config file: %s", pattern)
                return pattern

        logger.warning("Unable to automatically detect a Charles config path")
        return None

    def validate(self) -> list[str]:
        warnings: list[str] = []

        if not self.config_path:
            warnings.append("Charles config file was not found; backup and restore are unavailable.")

        if self.request_timeout <= 0:
            warnings.append(
                f"Invalid request timeout ({self.request_timeout}); falling back to 10 seconds."
            )
            self.request_timeout = 10

        if self.max_stoptime <= 0 or self.max_stoptime > 7200:
            warnings.append(
                f"Invalid max stop time ({self.max_stoptime}); falling back to 3600 seconds."
            )
            self.max_stoptime = 3600

        if self.charles_user == "admin" and self.charles_pass == "123456":
            warnings.append(
                "Using default credentials (admin/123456); "
                "set CHARLES_USER and CHARLES_PASS to custom values."
            )

        return warnings

    def to_dict(self) -> dict:
        return {
            "charles_user": self.charles_user,
            "charles_pass": "***" if self.charles_pass else None,
            "proxy_host": self.proxy_host,
            "proxy_port": self.proxy_port,
            "charles_base_url": self.charles_base_url,
            "charles_cli_path": self.charles_cli_path,
            "config_path": self.config_path,
            "profiles_dir": self.profiles_dir,
            "state_dir": self.state_dir,
            "package_dir": self.package_dir,
            "backup_dir": self.backup_dir,
            "request_timeout": self.request_timeout,
            "max_stoptime": self.max_stoptime,
            "manage_charles_lifecycle": self.manage_charles_lifecycle,
            "expose_legacy_tools": self.expose_legacy_tools,
            "reverse_state_dir": self.reverse_state_dir,
            "reverse_replay_timeout_seconds": self.reverse_replay_timeout_seconds,
            "reverse_live_session_ttl_seconds": self.reverse_live_session_ttl_seconds,
            "reverse_live_snapshot_history_limit": self.reverse_live_snapshot_history_limit,
            "reverse_max_query_limit": self.reverse_max_query_limit,
        }


_default_config: Optional[Config] = None


def get_config() -> Config:
    """Return the shared configuration instance."""
    global _default_config
    if _default_config is None:
        _default_config = Config.from_env()
    return _default_config


def reset_config() -> None:
    """Reset the shared configuration instance for tests and reloads."""
    global _default_config
    _default_config = None
