from charles_mcp.live_state import LiveCaptureManager


def _entry(
    *,
    host: str = "api.example.com",
    method: str = "GET",
    path: str = "/items",
    start: str = "2026-03-06T10:00:00.000+08:00",
) -> dict:
    return {
        "host": host,
        "method": method,
        "path": path,
        "times": {"start": start},
        "request": {"headers": []},
        "response": {"headers": []},
    }


def test_start_capture_creates_active_state() -> None:
    manager = LiveCaptureManager()

    capture = manager.start(managed=True, include_existing=False)

    assert capture.capture_id
    assert capture.status == "active"
    assert capture.cursor == 0
    assert capture.managed is True
    assert manager.active.capture_id == capture.capture_id


def test_read_commits_incremental_entries_and_advances_cursor() -> None:
    manager = LiveCaptureManager()
    capture = manager.start(managed=True, include_existing=False)

    first = manager.read(
        capture.capture_id,
        [_entry(path="/first")],
        cursor=0,
        limit=50,
    )
    second = manager.read(
        capture.capture_id,
        [_entry(path="/first"), _entry(path="/second", start="2026-03-06T10:00:01.000+08:00")],
        cursor=first.next_cursor,
        limit=50,
    )

    assert [item["path"] for item in first.items] == ["/first"]
    assert first.next_cursor == 1
    assert [item["path"] for item in second.items] == ["/second"]
    assert second.next_cursor == 2
    assert second.total_new_items == 1


def test_read_detects_session_reset() -> None:
    manager = LiveCaptureManager()
    capture = manager.start(managed=True, include_existing=False)

    manager.read(
        capture.capture_id,
        [
            _entry(path="/first"),
            _entry(path="/second", start="2026-03-06T10:00:01.000+08:00"),
        ],
        cursor=0,
        limit=50,
    )
    result = manager.read(
        capture.capture_id,
        [_entry(path="/replacement", start="2026-03-06T10:00:02.000+08:00")],
        cursor=2,
        limit=50,
    )

    assert result.status == "reset_detected"
    assert "session_reset_detected" in result.warnings
    assert [item["path"] for item in result.items] == ["/replacement"]
