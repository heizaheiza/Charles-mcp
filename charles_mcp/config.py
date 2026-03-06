"""
配置管理模块。

负责加载环境变量、自动检测 Charles 配置路径，以及管理全局配置。

环境变量:
    CHARLES_USER: Charles Web Interface 用户名 (默认: tower)
    CHARLES_PASS: Charles Web Interface 密码 (默认: 123456)
    CHARLES_PROXY_HOST: 代理主机 (默认: 127.0.0.1)
    CHARLES_PROXY_PORT: 代理端口 (默认: 8888)
    CHARLES_CONFIG_PATH: 手动指定 Charles 配置文件路径 (可选)
    CHARLES_REQUEST_TIMEOUT: HTTP 请求超时秒数 (默认: 10)
    CHARLES_MAX_STOPTIME: 最大录制时长秒数 (默认: 3600)
"""

import os
import sys
import glob
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable with a conservative default."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    """
    Charles MCP Server 配置类。

    从环境变量加载配置，并提供合理的默认值。
    自动检测 Charles 配置文件路径。

    Attributes:
        charles_user: Charles Web Interface 用户名
        charles_pass: Charles Web Interface 密码
        proxy_host: 代理主机地址
        proxy_port: 代理端口号
        charles_base_url: Charles 控制 API 的基础 URL
        config_path: Charles 配置文件路径
        profiles_dir: Charles profiles 目录路径
        base_dir: 项目基础目录
        package_dir: 流量包存储目录
        backup_dir: 配置备份目录
        request_timeout: HTTP 请求超时时间（秒）
        max_stoptime: 最大录制时长（秒）

    Example:
        >>> config = Config.from_env()
        >>> print(config.charles_base_url)
        'http://control.charles'
    """

    # 认证配置
    charles_user: str = field(default_factory=lambda: os.getenv("CHARLES_USER", "tower"))
    charles_pass: str = field(default_factory=lambda: os.getenv("CHARLES_PASS", "123456"))

    # 代理配置
    proxy_host: str = field(default_factory=lambda: os.getenv("CHARLES_PROXY_HOST", "127.0.0.1"))
    proxy_port: int = field(default_factory=lambda: int(os.getenv("CHARLES_PROXY_PORT", "8888")))

    # Charles API
    charles_base_url: str = "http://control.charles"

    # 路径配置
    config_path: Optional[str] = None
    profiles_dir: Optional[str] = None
    base_dir: str = field(default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    package_dir: str = ""
    backup_dir: str = ""

    # 超时与限制
    request_timeout: int = field(default_factory=lambda: int(os.getenv("CHARLES_REQUEST_TIMEOUT", "10")))
    max_stoptime: int = field(default_factory=lambda: int(os.getenv("CHARLES_MAX_STOPTIME", "3600")))
    manage_charles_lifecycle: bool = field(
        default_factory=lambda: _env_bool("CHARLES_MANAGE_LIFECYCLE", False)
    )

    def __post_init__(self) -> None:
        """初始化后处理：设置派生路径和自动检测配置文件。"""
        self.package_dir = os.path.join(self.base_dir, "package")
        self.backup_dir = os.path.join(self.base_dir, "back")

        # 尝试从环境变量获取配置路径，否则自动检测
        env_config_path = os.getenv("CHARLES_CONFIG_PATH")
        if env_config_path and os.path.exists(env_config_path):
            self.config_path = env_config_path
        else:
            self.config_path = self._detect_charles_config_path()

        # 设置 profiles 目录
        if self.config_path:
            self.profiles_dir = os.path.join(
                os.path.dirname(self.config_path), "data", "profiles"
            )

    @property
    def proxy_url(self) -> str:
        """获取代理 URL。"""
        return f"http://{self.proxy_host}:{self.proxy_port}"

    @property
    def proxies(self) -> dict[str, str]:
        """获取 httpx 格式的代理配置字典。"""
        return {
            "http://": self.proxy_url,
            "https://": self.proxy_url,
        }

    @property
    def auth(self) -> tuple[str, str]:
        """获取认证元组 (用于 httpx BasicAuth)。"""
        return (self.charles_user, self.charles_pass)

    @classmethod
    def from_env(cls) -> "Config":
        """
        从环境变量创建配置实例。

        Returns:
            Config: 配置实例

        Example:
            >>> config = Config.from_env()
            >>> config.charles_user
            'tower'
        """
        return cls()

    def _detect_charles_config_path(self) -> Optional[str]:
        """
        自动检测 Charles 配置文件路径。

        支持 Windows (包括 Microsoft Store 版本)、macOS 和 Linux。

        Returns:
            Optional[str]: 配置文件路径，未找到则返回 None
        """
        possible_patterns: list[str] = []

        if sys.platform == "win32":
            # Windows Microsoft Store 版本
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            if local_app_data:
                possible_patterns.append(
                    os.path.join(local_app_data, "Packages", "XK72.Charles_*", "RoamingState", "charles.config")
                )

            # Windows 传统安装版本
            app_data = os.environ.get("APPDATA", "")
            if app_data:
                possible_patterns.append(os.path.join(app_data, "Charles", "charles.config"))

            # 用户目录
            user_home = Path.home()
            possible_patterns.append(str(user_home / ".charles.config"))

        elif sys.platform == "darwin":
            # macOS
            user_home = Path.home()
            possible_patterns.extend([
                str(user_home / "Library" / "Application Support" / "Charles" / "charles.config"),
                str(user_home / ".charles.config"),
            ])

        else:
            # Linux 和其他 Unix 系统
            user_home = Path.home()
            xdg_config = os.environ.get("XDG_CONFIG_HOME", str(user_home / ".config"))
            possible_patterns.extend([
                os.path.join(xdg_config, "Charles", "charles.config"),
                str(user_home / ".charles.config"),
                str(user_home / ".charles" / "charles.config"),
            ])

        # 尝试匹配路径
        for pattern in possible_patterns:
            if "*" in pattern:
                # 使用 glob 匹配通配符
                matches = glob.glob(pattern)
                if matches:
                    config_path = matches[0]
                    logger.info(f"自动检测到 Charles 配置文件: {config_path}")
                    return config_path
            elif os.path.exists(pattern):
                logger.info(f"找到 Charles 配置文件: {pattern}")
                return pattern

        logger.warning("未能自动检测到 Charles 配置文件路径")
        return None

    def validate(self) -> list[str]:
        """
        验证配置有效性。

        Returns:
            list[str]: 验证警告信息列表
        """
        warnings: list[str] = []

        if not self.config_path:
            warnings.append("未找到 Charles 配置文件，备份/恢复功能将不可用")

        if self.request_timeout <= 0:
            warnings.append(f"请求超时时间无效 ({self.request_timeout})，将使用默认值 10")
            self.request_timeout = 10

        if self.max_stoptime <= 0 or self.max_stoptime > 7200:
            warnings.append(f"最大录制时长无效 ({self.max_stoptime})，将使用默认值 3600")
            self.max_stoptime = 3600

        # 检查是否使用默认凭据
        if self.charles_user == "tower" and self.charles_pass == "123456":
            warnings.append(
                "正在使用默认凭据 (tower/123456)，建议通过环境变量 "
                "CHARLES_USER 和 CHARLES_PASS 设置自定义凭据"
            )

        return warnings

    def to_dict(self) -> dict:
        """
        将配置转换为字典（隐藏敏感信息）。

        Returns:
            dict: 配置字典（密码被遮蔽）
        """
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


# 全局默认配置实例（延迟初始化）
_default_config: Optional[Config] = None


def get_config() -> Config:
    """
    获取全局配置实例（单例模式）。

    Returns:
        Config: 全局配置实例
    """
    global _default_config
    if _default_config is None:
        _default_config = Config.from_env()
    return _default_config


def reset_config() -> None:
    """重置全局配置实例（主要用于测试）。"""
    global _default_config
    _default_config = None
