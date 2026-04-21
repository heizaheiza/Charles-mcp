"""Official Charles Web Interface control and export helpers for vnext."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class CharlesControlConfig:
    user: str
    password: str
    base_url: str
    proxy_url: str
    timeout_seconds: float


class CharlesControlService:
    """Wrap official Charles Web Interface pages used by the vnext live tools."""

    def __init__(self, config: CharlesControlConfig) -> None:
        self.config = config

    async def get_recording_status(self) -> dict[str, object]:
        html = await self._get_text("/recording/")
        is_recording = "Status: Recording" in html and "Status: Recording Stopped" not in html
        return {
            "is_recording": is_recording,
            "status_text": "recording" if is_recording else "stopped",
            "page": html,
        }

    async def start_recording(self) -> None:
        await self._get_text("/recording/start")

    async def stop_recording(self) -> None:
        await self._get_text("/recording/stop")

    async def clear_session(self) -> None:
        await self._get_text("/session/clear")

    async def export_session_xml(self) -> str:
        return await self._get_text("/session/export-xml")

    async def download_session_native(self) -> bytes:
        return await self._get_bytes("/session/download")

    async def _get_text(self, path: str) -> str:
        async with self._client() as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.text

    async def _get_bytes(self, path: str) -> bytes:
        async with self._client() as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.content

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.config.base_url,
            auth=(self.config.user, self.config.password),
            proxy=self.config.proxy_url,
            timeout=self.config.timeout_seconds,
            follow_redirects=True,
        )
