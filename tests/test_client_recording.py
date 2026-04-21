import pytest

from charles_mcp.client import CharlesClient, CharlesClientError
from charles_mcp.config import Config


class _RecordingClient(CharlesClient):
    def __init__(
        self,
        *,
        clear_result: bool = True,
        start_result: bool = True,
        stop_result: bool = True,
        baseline_result: list[dict] | None = None,
        export_result: list[dict] | None = None,
    ) -> None:
        super().__init__(Config())
        self.clear_result = clear_result
        self.start_result = start_result
        self.stop_result = stop_result
        self.baseline_result = baseline_result or []
        self.export_result = export_result or []
        self.export_calls = 0

    async def clear_session(self) -> bool:
        return self.clear_result

    async def start_recording(self) -> bool:
        return self.start_result

    async def stop_recording(self) -> bool:
        return self.stop_result

    async def export_session_json(self) -> list[dict]:
        self.export_calls += 1
        if self.export_calls == 1:
            return list(self.baseline_result)
        return list(self.export_result)


@pytest.mark.asyncio
async def test_record_session_raises_when_clear_fails() -> None:
    client = _RecordingClient(clear_result=False)

    with pytest.raises(CharlesClientError, match="clear"):
        await client.record_session(1)


@pytest.mark.asyncio
async def test_record_session_raises_when_start_fails() -> None:
    client = _RecordingClient(start_result=False)

    with pytest.raises(CharlesClientError, match="start"):
        await client.record_session(1)


@pytest.mark.asyncio
async def test_record_session_raises_when_stop_fails() -> None:
    client = _RecordingClient(stop_result=False)

    with pytest.raises(CharlesClientError, match="stop"):
        await client.record_session(1)


@pytest.mark.asyncio
async def test_record_session_raises_when_export_is_empty() -> None:
    client = _RecordingClient(export_result=[])

    with pytest.raises(CharlesClientError, match="empty"):
        await client.record_session(1)


@pytest.mark.asyncio
async def test_record_session_raises_when_export_is_unchanged_from_baseline() -> None:
    stale_snapshot = [{"host": "api.example.com", "path": "/stale"}]
    client = _RecordingClient(
        baseline_result=stale_snapshot,
        export_result=stale_snapshot,
    )

    with pytest.raises(CharlesClientError, match="unchanged"):
        await client.record_session(1)
