"""History-oriented recording access for Charles MCP."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Optional, cast

from charles_mcp.client import CharlesClient
from charles_mcp.config import Config
from charles_mcp.schemas.history import (
    RecordedTrafficQueryResult,
    RecordingFileInfo,
    RecordingListResult,
    RecordingSnapshotResult,
)
from charles_mcp.utils import format_bytes, list_files_with_extension, validate_regex


class RecordingHistoryService:
    """Read and query saved Charles recording snapshots."""

    def __init__(self, config: Config, client_factory=CharlesClient) -> None:
        self.config = config
        self.client_factory = client_factory

    async def load_latest(self) -> list[dict]:
        async with self.client_factory(self.config) as client:
            return cast(list[dict], await client.load_latest_session())

    def _fallback_recording_path(self, client: CharlesClient) -> str | None:
        try:
            path = client.get_full_save_path()
        except Exception:
            return None

        try:
            return self._resolve_recording_path(path)
        except ValueError:
            return None

    def _latest_recording_path(self) -> str | None:
        files = list_files_with_extension(self.config.package_dir, ".chlsj")
        if not files:
            return None
        latest = sorted(files)[-1]
        return os.path.join(self.config.package_dir, latest)

    def _resolve_recording_path(self, path: str) -> str:
        package_dir = Path(self.config.package_dir).resolve()
        base_dir = Path(self.config.base_dir).resolve()
        candidate = Path(path)

        if not candidate.is_absolute():
            if candidate.parts and candidate.parts[0] == package_dir.name:
                candidate = base_dir / candidate
            else:
                candidate = package_dir / candidate

        resolved = candidate.resolve()
        try:
            resolved.relative_to(package_dir)
        except ValueError as exc:
            raise ValueError(
                f"recording_path must point to a .chlsj file inside {package_dir}"
            ) from exc

        if resolved.suffix.lower() != ".chlsj":
            raise ValueError("recording_path must end with `.chlsj`")

        return str(resolved)

    async def load_latest_with_path(self) -> tuple[str, list[dict]]:
        latest_path = self._latest_recording_path()

        async with self.client_factory(self.config) as client:
            raw_data = await client.load_latest_session()

            if latest_path:
                return latest_path, raw_data

            fallback_path = self._fallback_recording_path(client)
            if fallback_path:
                return fallback_path, raw_data

        raise FileNotFoundError(f"No saved recording found in: {self.config.package_dir}")

    async def query_latest(
        self,
        *,
        host_contains: Optional[str] = None,
        method_normalized: Optional[str] = None,
        keyword_regex: Optional[str] = None,
        keep_request: bool = True,
        keep_response: bool = True,
    ) -> list[dict]:
        raw_data = await self.load_latest()
        return self.filter_entries(
            raw_data,
            host_contains=host_contains,
            method_normalized=method_normalized,
            keyword_regex=keyword_regex,
            keep_request=keep_request,
            keep_response=keep_response,
        )

    async def query_latest_result(
        self,
        *,
        host_contains: Optional[str] = None,
        method_normalized: Optional[str] = None,
        keyword_regex: Optional[str] = None,
        keep_request: bool = True,
        keep_response: bool = True,
    ) -> RecordedTrafficQueryResult:
        try:
            latest_path, raw_data = await self.load_latest_with_path()
        except FileNotFoundError:
            return RecordedTrafficQueryResult(
                source="history",
                path=None,
                items=[],
                total_items=0,
                warnings=["no_saved_recordings"],
            )

        items = self.filter_entries(
            raw_data,
            host_contains=host_contains,
            method_normalized=method_normalized,
            keyword_regex=keyword_regex,
            keep_request=keep_request,
            keep_response=keep_response,
        )
        return RecordedTrafficQueryResult(
            source="history",
            path=latest_path,
            items=items,
            total_items=len(items),
        )

    def list_recordings(self) -> list[dict]:
        files = list_files_with_extension(self.config.package_dir, ".chlsj")
        result: list[dict] = []
        for filename in sorted(files):
            filepath = os.path.join(self.config.package_dir, filename)
            try:
                stat = os.stat(filepath)
                result.append(
                    {
                        "filename": filename,
                        "size": format_bytes(stat.st_size),
                        "size_bytes": stat.st_size,
                        "path": filepath,
                    }
                )
            except OSError:
                result.append({"filename": filename, "error": "unable_to_read_file_metadata"})
        return result

    def list_recordings_result(self) -> RecordingListResult:
        items: list[RecordingFileInfo] = []
        warnings: list[str] = []
        for record in self.list_recordings():
            if "error" in record:
                continue
            items.append(RecordingFileInfo(**record))

        if not items:
            warnings.append("no_saved_recordings")

        return RecordingListResult(
            items=items,
            total_items=len(items),
            warnings=warnings,
        )

    async def get_snapshot(self, path: Optional[str] = None) -> list[dict]:
        if path:
            resolved_path = self._resolve_recording_path(path)
            with open(resolved_path, "r", encoding="utf-8") as handle:
                return cast(list[dict], json.load(handle))
        return await self.load_latest()

    async def get_snapshot_result(self, path: Optional[str] = None) -> RecordingSnapshotResult:
        if path:
            resolved_path = self._resolve_recording_path(path)
            with open(resolved_path, "r", encoding="utf-8") as handle:
                items = cast(list[dict], json.load(handle))
            return RecordingSnapshotResult(
                source="history",
                path=resolved_path,
                items=items,
                total_items=len(items),
            )

        try:
            latest_path, items = await self.load_latest_with_path()
        except FileNotFoundError:
            return RecordingSnapshotResult(
                source="history",
                path=None,
                items=[],
                total_items=0,
                warnings=["no_saved_recordings"],
            )

        return RecordingSnapshotResult(
            source="history",
            path=latest_path,
            items=items,
            total_items=len(items),
        )

    def validate_keyword_regex(self, keyword_regex: Optional[str]) -> tuple[bool, Optional[str]]:
        if not keyword_regex:
            return (True, None)
        return validate_regex(keyword_regex)

    def filter_entries(
        self,
        raw_data: list[dict],
        *,
        host_contains: Optional[str] = None,
        method_normalized: Optional[str] = None,
        keyword_regex: Optional[str] = None,
        keep_request: bool = True,
        keep_response: bool = True,
    ) -> list[dict]:
        filtered_results: list[dict] = []
        compiled_regex = re.compile(keyword_regex, re.IGNORECASE) if keyword_regex else None

        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            if "error" in entry and len(entry) == 1:
                return raw_data

            if host_contains and host_contains.lower() not in entry.get("host", "").lower():
                continue

            if method_normalized and method_normalized != entry.get("method", "").upper():
                continue

            match_info: Optional[dict] = None
            if compiled_regex:
                try:
                    entry_str = json.dumps(
                        entry,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    match = compiled_regex.search(entry_str)
                except (TimeoutError, RecursionError):
                    return [{"error": "regex_match_timeout"}]

                if not match:
                    continue
                snippet_start = max(match.start() - 40, 0)
                snippet_end = min(match.end() + 40, len(entry_str))
                match_info = {
                    "line": 1,
                    "content": entry_str[snippet_start:snippet_end],
                }

            result = deepcopy(entry)
            if not keep_request:
                result.pop("request", None)
            if not keep_response:
                result.pop("response", None)
            if match_info:
                result["_match_location"] = match_info
            filtered_results.append(result)

        return filtered_results
