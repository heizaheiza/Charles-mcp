"""Live capture polling service for Charles MCP."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

from charles_mcp.client import CharlesClient, CharlesClientError
from charles_mcp.config import Config
from charles_mcp.live_state import LiveCaptureManager
from charles_mcp.schemas.live_capture import (
    LiveCaptureReadResult,
    LiveCaptureStartResult,
    StopLiveCaptureResult,
)
from charles_mcp.utils import ensure_directory

logger = logging.getLogger(__name__)

STOP_RETRY_DELAY_SECONDS = 0.25


class LiveCaptureService:
    """Operate on the current Charles session as a pseudo-realtime stream."""

    def __init__(
        self,
        config: Config,
        *,
        client_factory=CharlesClient,
        live_manager: Optional[LiveCaptureManager] = None,
    ) -> None:
        self.config = config
        self.client_factory = client_factory
        self.live_manager = live_manager or LiveCaptureManager()
        self._shared_client: Optional[CharlesClient] = None

    async def _get_shared_client(self) -> CharlesClient:
        """Return the reusable client, creating it on first access."""
        if self._shared_client is None:
            self._shared_client = self.client_factory(self.config)
            await self._shared_client.connect()
        return self._shared_client

    async def _close_shared_client(self) -> None:
        """Close the shared client if it exists."""
        if self._shared_client is not None:
            try:
                await self._shared_client.close()
            except Exception as exc:
                logger.debug("Error closing shared client: %s", exc)
            finally:
                self._shared_client = None

    async def start(
        self,
        *,
        reset_session: bool = True,
        include_existing: bool = False,
        adopt_existing: bool = False,
    ) -> LiveCaptureStartResult:
        managed = not adopt_existing
        baseline_items: list[dict] = []

        client = await self._get_shared_client()
        if adopt_existing:
            baseline_items = await client.export_session_json()
        else:
            if not reset_session:
                baseline_items = await client.export_session_json()
            if reset_session and not await client.clear_session():
                raise CharlesClientError("failed to clear current Charles session")
            if not await client.start_recording():
                raise CharlesClientError("failed to start Charles recording")

        capture = self.live_manager.start(
            managed=managed,
            include_existing=include_existing,
            baseline_items=baseline_items,
        )

        return LiveCaptureStartResult(
            capture_id=capture.capture_id,
            status="active",
            managed=managed,
            include_existing=include_existing,
        )

    async def read(
        self,
        capture_id: str,
        *,
        cursor: Optional[int] = None,
        limit: int = 50,
        advance: bool = True,
    ) -> LiveCaptureReadResult:
        raw_items = await self.export_current_session()
        return self.live_manager.read(
            capture_id,
            raw_items,
            cursor=cursor,
            limit=limit,
            advance=advance,
        )

    async def stop(
        self,
        capture_id: str,
        *,
        persist: bool = True,
    ) -> StopLiveCaptureResult:
        capture = self.live_manager.require(capture_id)
        raw_items = await self.export_current_session()
        self.live_manager.read(
            capture_id,
            raw_items,
            cursor=capture.cursor,
            limit=max(len(raw_items), 1),
            advance=True,
        )

        if capture.managed:
            stop_succeeded, stop_warnings, stop_error = await self._stop_recording_with_retry()
            capture.warnings = list(dict.fromkeys(capture.warnings + stop_warnings))
            if not stop_succeeded:
                return StopLiveCaptureResult(
                    capture_id=capture.capture_id,
                    status="stop_failed",
                    persisted_path=None,
                    total_items=len(capture.items),
                    recoverable=True,
                    active_capture_preserved=True,
                    error=stop_error or "failed to stop Charles recording",
                    warnings=list(capture.warnings),
                )

        persisted_path: str | None = None
        if persist:
            client = await self._get_shared_client()
            persisted_path = self.save_capture_items(
                client.get_full_save_path(),
                capture.items,
            )

        stopped = self.live_manager.close(capture_id)
        await self._close_shared_client()
        return StopLiveCaptureResult(
            capture_id=stopped.capture_id,
            status="stopped",
            persisted_path=persisted_path,
            total_items=len(stopped.items),
            recoverable=False,
            active_capture_preserved=False,
            error=None,
            warnings=stopped.warnings,
        )

    async def export_current_session(self) -> list[dict]:
        try:
            client = await self._get_shared_client()
            return await client.export_session_json()
        except CharlesClientError:
            # Shared client may have gone stale; reset and retry once
            await self._close_shared_client()
            client = await self._get_shared_client()
            return await client.export_session_json()

    def save_capture_items(self, path: str, data: list[dict]) -> str:
        ensure_directory(os.path.dirname(path) or self.config.package_dir)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        return path

    def get_active_capture(self) -> dict | None:
        capture = self.live_manager.active
        if capture is None:
            return None
        return {
            "capture_id": capture.capture_id,
            "status": capture.status,
            "managed": capture.managed,
            "include_existing": capture.include_existing,
            "cursor": capture.cursor,
            "started_at": capture.started_at,
            "warnings": list(capture.warnings),
        }

    async def _stop_recording_with_retry(self) -> tuple[bool, list[str], str | None]:
        warnings: list[str] = []
        last_error: str | None = None

        for attempt in range(2):
            try:
                client = await self._get_shared_client()
                success = await client.stop_recording()
            except CharlesClientError as error:
                success = False
                last_error = str(error)
            else:
                if success:
                    if attempt > 0:
                        warnings.append("stop_recording_retry_succeeded")
                    return True, warnings, None
                last_error = "failed to stop Charles recording"

            if attempt == 0:
                await asyncio.sleep(STOP_RETRY_DELAY_SECONDS)

        warnings.append("stop_recording_failed_after_retry")
        return False, warnings, last_error or "failed to stop Charles recording"

