"""
Charles API 异步客户端模块。

封装与 Charles Proxy Web Interface 的所有 HTTP 交互，
使用 httpx 异步客户端确保不阻塞事件循环。
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Any, Callable
from pathlib import Path

import httpx

from charles_mcp.config import Config, get_config
from charles_mcp.utils import ensure_directory, get_latest_file

logger = logging.getLogger(__name__)


class CharlesClientError(Exception):
    """Charles 客户端错误基类。"""
    pass


class CharlesConnectionError(CharlesClientError):
    """Charles 连接错误。"""
    pass


class CharlesAPIError(CharlesClientError):
    """Charles API 调用错误。"""
    pass


class CharlesClient:
    """
    Charles Proxy 异步 API 客户端。

    提供对 Charles Web Interface 的完整异步访问，包括：
    - 会话管理（清理、导出）
    - 录制控制（开始、停止）
    - 网络节流（弱网模拟）
    - 配置管理

    Attributes:
        config: 配置对象
        _client: httpx 异步客户端实例

    Example:
        >>> async with CharlesClient() as client:
        ...     await client.clear_session()
        ...     await asyncio.sleep(30)
        ...     data = await client.export_session_json()
    """

    # 预设的网络节流配置
    THROTTLE_PRESETS = {
        "3g": "3G",
        "4g": "4G",
        "5g": "5G",
        "fibre": "100+Mbps+Fibre",
        "100mbps": "100+Mbps+Fibre",
        "56k": "56+kbps+Modem",
        "256k": "256+kbps+ISDN/DSL",
        "deactivate": "deactivate",
        "off": "deactivate",
    }

    def __init__(self, config: Optional[Config] = None) -> None:
        """
        初始化 Charles 客户端。

        Args:
            config: 配置对象，如果为 None 则使用全局配置
        """
        self.config = config or get_config()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "CharlesClient":
        """异步上下文管理器入口。"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口。"""
        await self.close()

    async def connect(self) -> None:
        """
        建立与 Charles 的连接（创建 httpx 客户端）。

        Raises:
            CharlesConnectionError: 连接失败时抛出
        """
        if self._client is not None:
            return

        try:
            self._client = httpx.AsyncClient(
                base_url=self.config.charles_base_url,
                auth=httpx.BasicAuth(*self.config.auth),
                proxy=self.config.proxy_url,
                timeout=httpx.Timeout(self.config.request_timeout),
                follow_redirects=True,
            )
            logger.info("Charles 客户端已连接")
        except Exception as e:
            raise CharlesConnectionError(f"无法创建 Charles 客户端: {e}") from e

    async def close(self) -> None:
        """关闭客户端连接。"""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as e:
                logger.warning(f"关闭客户端时出错: {e}")
            finally:
                self._client = None
                logger.info("Charles 客户端已关闭")

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        发送 HTTP 请求到 Charles API。

        Args:
            method: HTTP 方法 (GET, POST, etc.)
            endpoint: API 端点路径
            **kwargs: 传递给 httpx 的额外参数

        Returns:
            httpx.Response: HTTP 响应对象

        Raises:
            CharlesConnectionError: 连接问题
            CharlesAPIError: API 调用失败
        """
        if self._client is None:
            await self.connect()

        try:
            response = await self._client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response
        except httpx.ConnectError as e:
            raise CharlesConnectionError(
                f"无法连接到 Charles ({self.config.charles_base_url}): {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise CharlesConnectionError(f"请求超时: {e}") from e
        except httpx.HTTPStatusError as e:
            raise CharlesAPIError(
                f"API 调用失败 [{e.response.status_code}]: {endpoint}"
            ) from e
        except httpx.RequestError as e:
            raise CharlesClientError(f"请求错误: {e}") from e

    async def _get(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        """发送 GET 请求。"""
        return await self._request("GET", endpoint, **kwargs)

    # ==================== 会话管理 ====================

    async def clear_session(self) -> bool:
        """
        清理当前 Charles 会话数据。

        Returns:
            bool: 是否成功

        Example:
            >>> await client.clear_session()
            True
        """
        try:
            await self._get("/session/clear")
            logger.info("Charles 会话已清理")
            return True
        except CharlesClientError as e:
            logger.error(f"清理会话失败: {e}")
            return False

    async def export_session_json(self) -> list[dict]:
        """
        导出当前会话为 JSON 格式。

        Returns:
            list[dict]: 会话数据列表

        Raises:
            CharlesAPIError: 导出失败时抛出
        """
        try:
            response = await self._get("/session/export-json")
            data = response.json()
            logger.info(f"导出会话成功，共 {len(data)} 条记录")
            return data
        except json.JSONDecodeError as e:
            raise CharlesAPIError(f"解析 JSON 响应失败: {e}") from e

    async def export_session_text(self) -> str:
        """
        导出当前会话为文本格式。

        Returns:
            str: 会话数据文本
        """
        response = await self._get("/session/export-text")
        return response.text

    # ==================== 录制控制 ====================

    async def start_recording(self) -> bool:
        """
        开始录制流量。

        Returns:
            bool: 是否成功
        """
        try:
            await self._get("/recording/start")
            logger.info("开始录制流量")
            return True
        except CharlesClientError as e:
            logger.error(f"开始录制失败: {e}")
            return False

    async def stop_recording(self) -> bool:
        """
        停止录制流量。

        Returns:
            bool: 是否成功
        """
        try:
            await self._get("/recording/stop")
            logger.info("停止录制流量")
            return True
        except CharlesClientError as e:
            logger.error(f"停止录制失败: {e}")
            return False

    # ==================== 网络节流 ====================

    async def activate_throttling(self, preset: str) -> bool:
        """
        激活网络节流。

        Args:
            preset: 预设名称（如 '3G', '4G', 'Fibre' 等）

        Returns:
            bool: 是否成功

        Example:
            >>> await client.activate_throttling("3G")
            True
        """
        # 规范化预设名称
        normalized = self.THROTTLE_PRESETS.get(preset.lower(), preset)

        try:
            await self._get(f"/throttling/activate", params={"preset": normalized})
            logger.info(f"网络节流已激活: {normalized}")
            return True
        except CharlesClientError as e:
            logger.error(f"激活网络节流失败: {e}")
            return False

    async def deactivate_throttling(self) -> bool:
        """
        停用网络节流。

        Returns:
            bool: 是否成功
        """
        try:
            await self._get("/throttling/deactivate")
            logger.info("网络节流已停用")
            return True
        except CharlesClientError as e:
            logger.error(f"停用网络节流失败: {e}")
            return False

    async def set_throttling(self, status: str) -> tuple[bool, str]:
        """
        设置网络节流状态。

        统一入口，支持激活和停用。

        Args:
            status: 预设名称或 'deactivate'/'off' 来停用

        Returns:
            tuple[bool, str]: (是否成功, 状态消息)

        Example:
            >>> await client.set_throttling("3G")
            (True, "已激活网络节流: 3G")
            >>> await client.set_throttling("off")
            (True, "已停用网络节流")
        """
        normalized = self.THROTTLE_PRESETS.get(status.lower(), status)

        if normalized == "deactivate":
            success = await self.deactivate_throttling()
            return (success, "已停用网络节流" if success else "停用网络节流失败")
        else:
            success = await self.activate_throttling(normalized)
            return (
                success,
                f"已激活网络节流: {normalized}" if success else f"激活网络节流失败: {normalized}"
            )

    # ==================== Charles 控制 ====================

    async def quit_charles(self, timeout: float = 3.0) -> bool:
        """
        退出 Charles 程序。

        Args:
            timeout: 请求超时时间

        Returns:
            bool: 是否成功发送退出命令
        """
        if self._client is None:
            await self.connect()

        try:
            # 退出命令可能不会返回响应，使用短超时
            await self._client.get(
                "/quit",
                timeout=httpx.Timeout(timeout),
            )
            return True
        except (httpx.TimeoutException, httpx.RequestError) as e:
            # 退出命令通常会导致连接中断，这是预期行为
            logger.debug(f"Charles 退出命令已发送 (预期的连接中断): {e}")
            return True
        except Exception as e:
            logger.warning(f"发送退出命令时出错: {e}")
            return False

    async def get_info(self) -> Optional[dict]:
        """
        获取 Charles 信息。

        Returns:
            Optional[dict]: Charles 信息，失败返回 None
        """
        try:
            response = await self._get("/")
            return {"status": "connected", "response": response.text[:200]}
        except CharlesClientError as e:
            logger.error(f"获取 Charles 信息失败: {e}")
            return None

    # ==================== 高级功能 ====================

    async def record_session(
        self,
        duration: int,
        save_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], Any]] = None,
    ) -> list[dict]:
        """
        录制指定时长的流量会话。

        Args:
            duration: 录制时长（秒）
            save_path: 保存路径（可选）
            progress_callback: 进度回调函数，签名为 (current: int, total: int) -> None

        Returns:
            list[dict]: 录制的流量数据

        Raises:
            CharlesAPIError: 录制失败时抛出
            ValueError: 参数无效时抛出

        Example:
            >>> data = await client.record_session(30, "/tmp/session.json")
        """
        if duration <= 0:
            raise ValueError("录制时长必须大于 0")

        logger.info(f"开始录制会话，时长: {duration}秒")
        baseline_snapshot = await self.export_session_json()

        # 清理旧数据并开始录制
        if not await self.clear_session():
            raise CharlesClientError("failed to clear Charles session before recording")
        if not await self.start_recording():
            raise CharlesClientError("failed to start Charles recording")

        # 等待录制，定期报告进度
        interval = min(10, duration)
        elapsed = 0

        while elapsed < duration:
            remaining = duration - elapsed
            wait_time = min(interval, remaining)

            if progress_callback:
                try:
                    result = progress_callback(elapsed, duration)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.warning(f"进度回调出错: {e}")

            await asyncio.sleep(wait_time)
            elapsed += wait_time

        # 最终进度
        if progress_callback:
            try:
                result = progress_callback(duration, duration)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

        # 停止录制并导出
        if not await self.stop_recording():
            raise CharlesClientError("failed to stop Charles recording")
        data = await self.export_session_json()
        if not data:
            raise CharlesClientError("recording export is empty")
        if baseline_snapshot and data == baseline_snapshot:
            raise CharlesClientError("recording export is unchanged from baseline")

        # 保存到文件
        if save_path:
            try:
                ensure_directory(str(Path(save_path).parent))
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"会话已保存: {save_path}")
            except OSError as e:
                logger.error(f"保存会话失败: {e}")
                raise CharlesClientError(f"failed to persist recording snapshot: {e}") from e

        return data

    async def load_latest_session(self, package_dir: Optional[str] = None) -> list[dict]:
        """
        加载最新的会话文件。

        Args:
            package_dir: 流量包目录，默认使用配置中的目录

        Returns:
            list[dict]: 会话数据

        Raises:
            FileNotFoundError: 未找到会话文件
        """
        directory = package_dir or self.config.package_dir
        latest_file = get_latest_file(directory, ".chlsj")

        if not latest_file:
            raise FileNotFoundError(f"未找到历史流量包: {directory}")

        logger.info(f"加载历史会话: {latest_file}")

        with open(latest_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_filename(self) -> str:
        """
        生成带时间戳的文件名。

        Returns:
            str: 文件名（不含路径）
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{timestamp}.chlsj"

    def get_full_save_path(self) -> str:
        """
        获取完整的保存路径。

        Returns:
            str: 完整文件路径
        """
        ensure_directory(self.config.package_dir)
        return str(Path(self.config.package_dir) / self.generate_filename())
