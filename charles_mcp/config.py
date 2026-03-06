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


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable with a conservative default."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    """Runtime configuration for the Charles MCP server."""

    charles_user: str = field(default_factory=lambda: os.getenv("CHARLES_USER", "admin"))
    charles_pass: str = field(default_factory=lambda: os.getenv("CHARLES_PASS", "123456"))

    proxy_host: str = field(default_factory=lambda: os.getenv("CHARLES_PROXY_HOST", "127.0.0.1"))
    proxy_port: int = field(default_factory=lambda: int(os.getenv("CHARLES_PROXY_PORT", "8888")))

    charles_base_url: str = "http://control.charles"

    config_path: Optional[str] = None
    profiles_dir: Optional[str] = None
    base_dir: str = field(
        default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
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

    def __post_init__(self) -> None:
        self.package_dir = os.path.join(self.base_dir, "package")
        self.backup_dir = os.path.join(self.base_dir, "back")

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
            "config_path": self.config_path,
            "profiles_dir": self.profiles_dir,
            "package_dir": self.package_dir,
            "backup_dir": self.backup_dir,
            "request_timeout": self.request_timeout,
            "max_stoptime": self.max_stoptime,
            "manage_charles_lifecycle": self.manage_charles_lifecycle,
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
