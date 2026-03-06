"""配置模块单元测试。"""

import os
import sys
import pytest
from unittest.mock import patch

from charles_mcp.config import Config, get_config, reset_config


class TestConfig:
    """Config 类测试。"""

    def setup_method(self) -> None:
        """每个测试方法前重置全局配置。"""
        reset_config()

    def test_default_values(self) -> None:
        """测试默认配置值。"""
        config = Config()
        assert config.charles_user == "tower"
        assert config.charles_pass == "123456"
        assert config.proxy_host == "127.0.0.1"
        assert config.proxy_port == 8888
        assert config.charles_base_url == "http://control.charles"
        assert config.request_timeout == 10
        assert config.max_stoptime == 3600

    def test_from_env(self) -> None:
        """测试从环境变量加载配置。"""
        with patch.dict(os.environ, {
            "CHARLES_USER": "testuser",
            "CHARLES_PASS": "testpass",
            "CHARLES_PROXY_PORT": "9999",
        }):
            reset_config()
            config = Config.from_env()
            assert config.charles_user == "testuser"
            assert config.charles_pass == "testpass"
            assert config.proxy_port == 9999

    def test_proxy_url(self) -> None:
        """测试代理 URL 生成。"""
        config = Config()
        assert config.proxy_url == "http://127.0.0.1:8888"

    def test_auth_tuple(self) -> None:
        """测试认证元组。"""
        config = Config()
        assert config.auth == ("tower", "123456")

    def test_proxies_dict(self) -> None:
        """测试代理字典格式。"""
        config = Config()
        proxies = config.proxies
        assert "http://" in proxies
        assert "https://" in proxies

    def test_to_dict_hides_password(self) -> None:
        """测试 to_dict 隐藏密码。"""
        config = Config()
        d = config.to_dict()
        assert d["charles_pass"] == "***"
        assert d["charles_user"] == "tower"

    def test_validate_valid_config(self) -> None:
        """测试有效配置的验证。"""
        config = Config()
        config.config_path = "/some/path"
        warnings = config.validate()
        assert len(warnings) == 0 or all("配置文件" not in w for w in warnings)

    def test_validate_invalid_timeout(self) -> None:
        """测试无效超时值的验证。"""
        config = Config()
        config.request_timeout = -1
        config.config_path = "/some/path"
        warnings = config.validate()
        assert any("超时" in w for w in warnings)
        assert config.request_timeout == 10  # 被重置为默认值

    def test_validate_invalid_max_stoptime(self) -> None:
        """测试无效最大录制时长的验证。"""
        config = Config()
        config.max_stoptime = 99999
        config.config_path = "/some/path"
        warnings = config.validate()
        assert any("录制时长" in w for w in warnings)
        assert config.max_stoptime == 3600  # 被重置为默认值

    def test_singleton(self) -> None:
        """测试全局配置单例。"""
        reset_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_detect_config_path_windows(self) -> None:
        """测试 Windows 路径检测（仅在 Windows 上运行）。"""
        if sys.platform != "win32":
            pytest.skip("仅在 Windows 上运行")

        config = Config()
        # 在 Windows 上应该尝试检测路径（结果取决于是否安装了 Charles）
        # 这里只验证不会抛出异常
        assert isinstance(config.config_path, (str, type(None)))


class TestUtils:
    """utils 模块测试。"""

    def test_validate_regex_valid(self) -> None:
        """测试有效正则表达式。"""
        from charles_mcp.utils import validate_regex
        valid, error = validate_regex(r"\d+")
        assert valid is True
        assert error is None

    def test_validate_regex_invalid(self) -> None:
        """测试无效正则表达式。"""
        from charles_mcp.utils import validate_regex
        valid, error = validate_regex(r"[invalid")
        assert valid is False
        assert error is not None

    def test_format_bytes(self) -> None:
        """测试字节格式化。"""
        from charles_mcp.utils import format_bytes
        assert "B" in format_bytes(500)
        assert "KB" in format_bytes(1536)
        assert "MB" in format_bytes(1048576)
