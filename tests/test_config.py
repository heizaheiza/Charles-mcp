"""Unit tests for configuration helpers."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import charles_mcp.config as config_module
from charles_mcp.config import Config, get_config, reset_config


class TestConfig:
    """Tests for the Config dataclass."""

    def setup_method(self) -> None:
        """Reset the shared config before each test."""
        reset_config()

    def test_default_values(self) -> None:
        config = Config()
        assert config.charles_user == "admin"
        assert config.charles_pass == "123456"
        assert config.proxy_host == "127.0.0.1"
        assert config.proxy_port == 8888
        assert config.charles_base_url == "http://control.charles"
        assert config.request_timeout == 10
        assert config.max_stoptime == 3600
        assert config.expose_legacy_tools is False

    def test_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CHARLES_USER": "testuser",
                "CHARLES_PASS": "testpass",
                "CHARLES_PROXY_PORT": "9999",
                "CHARLES_EXPOSE_LEGACY_TOOLS": "true",
            },
        ):
            reset_config()
            config = Config.from_env()
            assert config.charles_user == "testuser"
            assert config.charles_pass == "testpass"
            assert config.proxy_port == 9999
            assert config.expose_legacy_tools is True

    def test_explicit_base_dir_keeps_runtime_artifacts_under_base_dir(
        self,
        tmp_path: Path,
    ) -> None:
        config = Config(base_dir=str(tmp_path))

        assert config.package_dir == str(tmp_path / "package")
        assert config.backup_dir == str(tmp_path / "back")

    def test_default_install_layout_uses_user_state_dir(self, tmp_path: Path) -> None:
        install_root = tmp_path / "site-packages" / "charles-mcp"
        install_root.mkdir(parents=True, exist_ok=True)
        state_root = tmp_path / "state-root"

        with patch.object(config_module, "_default_base_dir", return_value=str(install_root)):
            with patch.object(config_module, "_default_state_dir", return_value=str(state_root)):
                config = Config(base_dir=str(install_root))

        assert config.base_dir == str(install_root)
        assert config.package_dir == str(state_root / "package")
        assert config.backup_dir == str(state_root / "back")

    def test_proxy_url(self) -> None:
        config = Config()
        assert config.proxy_url == "http://127.0.0.1:8888"

    def test_auth_tuple(self) -> None:
        config = Config()
        assert config.auth == ("admin", "123456")

    def test_proxies_dict(self) -> None:
        config = Config()
        proxies = config.proxies
        assert "http://" in proxies
        assert "https://" in proxies

    def test_to_dict_hides_password(self) -> None:
        config = Config()
        data = config.to_dict()
        assert data["charles_pass"] == "***"
        assert data["charles_user"] == "admin"

    def test_validate_valid_config(self) -> None:
        config = Config()
        config.config_path = "/some/path"
        warnings = config.validate()
        assert len(warnings) == 0 or all("config" not in warning.lower() for warning in warnings)

    def test_validate_invalid_timeout(self) -> None:
        config = Config()
        config.request_timeout = -1
        config.config_path = "/some/path"
        warnings = config.validate()
        assert warnings
        assert config.request_timeout == 10

    def test_validate_invalid_max_stoptime(self) -> None:
        config = Config()
        config.max_stoptime = 99999
        config.config_path = "/some/path"
        warnings = config.validate()
        assert warnings
        assert config.max_stoptime == 3600

    def test_singleton(self) -> None:
        reset_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_detect_config_path_windows(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows-only detection test")

        config = Config()
        assert isinstance(config.config_path, (str, type(None)))


class TestUtils:
    """Tests for utility helpers used by config flows."""

    def test_validate_regex_valid(self) -> None:
        from charles_mcp.utils import validate_regex

        valid, error = validate_regex(r"\d+")
        assert valid is True
        assert error is None

    def test_validate_regex_invalid(self) -> None:
        from charles_mcp.utils import validate_regex

        valid, error = validate_regex(r"[invalid")
        assert valid is False
        assert error is not None

    def test_format_bytes(self) -> None:
        from charles_mcp.utils import format_bytes

        assert "B" in format_bytes(500)
        assert "KB" in format_bytes(1536)
        assert "MB" in format_bytes(1048576)
