# Charles Live Capture Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 agent 能在 Charles 正在录制时稳定读取当前录制中的增量数据，并彻底区分实时读取与历史查询通路。

**Architecture:** 基于现有 `CharlesClient.export_session_json()` 和 Charles 当前 session 导出能力，在 MCP server 内引入 `LiveCaptureManager` 维护活跃 capture 状态、cursor、去重索引和会话隔离规则。实时链路只读取当前 session 并返回增量；历史链路只读取落盘 recording，禁止任何跨链路 fallback。随后再把 tool/schema/error/logging 统一起来，形成“控制类 tool + 实时读取类 tool + 历史查询类 tool”的稳定接口。

**Tech Stack:** Python 3.10+, MCP Python SDK (FastMCP), Pydantic v2, httpx, asyncio, pytest, pytest-asyncio

---

### Task 1: 建立活跃 capture 状态管理器

**Files:**
- Create: `charles_mcp/live_state.py`
- Modify: `charles_mcp/server.py`
- Test: `tests/test_live_state.py`

**Step 1: Write the failing test**

```python
from charles_mcp.live_state import LiveCaptureManager


def test_start_capture_creates_active_state():
    manager = LiveCaptureManager()
    capture = manager.start(managed=True, include_existing=False)
    assert capture.capture_id
    assert capture.status == "active"
    assert capture.cursor == 0
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_live_state.py -q`
Expected: FAIL because `LiveCaptureManager` does not exist

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class LiveCaptureState:
    capture_id: str
    status: str
    cursor: int = 0
    seen_keys: set[str] = field(default_factory=set)


class LiveCaptureManager:
    def __init__(self) -> None:
        self.active: LiveCaptureState | None = None

    def start(self, managed: bool, include_existing: bool) -> LiveCaptureState:
        self.active = LiveCaptureState(capture_id=str(uuid4()), status="active")
        return self.active
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_live_state.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/live_state.py charles_mcp/server.py tests/test_live_state.py
git commit -m "feat: add live capture runtime state manager"
```

### Task 2: 引入实时读取 tool，并禁止 fallback 到历史文件

**Files:**
- Modify: `charles_mcp/server.py`
- Modify: `charles_mcp/client.py`
- Create: `charles_mcp/schemas/live_capture.py`
- Test: `tests/test_live_capture_tools.py`

**Step 1: Write the failing test**

```python
async def test_read_live_capture_never_loads_latest_file(mocker):
    client = mocker.AsyncMock()
    client.export_session_json.return_value = []
    client.load_latest_session.side_effect = AssertionError("history path must not be used")
    ...
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_live_capture_tools.py -q`
Expected: FAIL because no live capture tool exists

**Step 3: Write minimal implementation**

```python
@mcp.tool()
async def read_live_capture(capture_id: str, cursor: int | None = None) -> LiveCaptureReadResult:
    capture = live_manager.require(capture_id)
    raw_items = await client.export_session_json()
    return live_manager.diff(capture, raw_items, cursor=cursor)
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_live_capture_tools.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/server.py charles_mcp/client.py charles_mcp/schemas/live_capture.py tests/test_live_capture_tools.py
git commit -m "feat: add live capture read path without history fallback"
```

### Task 3: 拆分实时工具与历史工具

**Files:**
- Create: `charles_mcp/tools/live_tools.py`
- Create: `charles_mcp/tools/history_tools.py`
- Modify: `charles_mcp/server.py`
- Test: `tests/test_history_tools.py`

**Step 1: Write the failing test**

```python
def test_history_tools_only_use_recordings():
    ...


def test_live_tools_only_use_current_session():
    ...
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_history_tools.py tests/test_live_capture_tools.py -q`
Expected: FAIL because tool semantics are still mixed in `_get_proxy_data()`

**Step 3: Write minimal implementation**

```python
def register_live_tools(mcp, services): ...
def register_history_tools(mcp, services): ...
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_history_tools.py tests/test_live_capture_tools.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/tools/live_tools.py charles_mcp/tools/history_tools.py charles_mcp/server.py tests/test_history_tools.py
git commit -m "refactor: split live capture and recording history tools"
```

### Task 4: 统一实时返回结构与 cursor 语义

**Files:**
- Modify: `charles_mcp/schemas/live_capture.py`
- Modify: `charles_mcp/live_state.py`
- Modify: `charles_mcp/tools/live_tools.py`
- Test: `tests/test_live_cursor_contract.py`

**Step 1: Write the failing test**

```python
def test_live_read_response_contains_cursor_and_status():
    ...
    assert result.capture_id
    assert result.status == "active"
    assert isinstance(result.next_cursor, int)
    assert isinstance(result.total_new_items, int)
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_live_cursor_contract.py -q`
Expected: FAIL because response schema is not yet explicit

**Step 3: Write minimal implementation**

```python
class LiveCaptureReadResult(BaseModel):
    capture_id: str
    status: Literal["active", "idle", "stopped", "reset_detected"]
    items: list[SessionEntry]
    next_cursor: int
    total_new_items: int
    truncated: bool = False
    warnings: list[str] = []
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_live_cursor_contract.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/schemas/live_capture.py charles_mcp/live_state.py charles_mcp/tools/live_tools.py tests/test_live_cursor_contract.py
git commit -m "refactor: standardize live capture cursor contract"
```

### Task 5: 增加 start/peek/stop 管理接口与录制隔离

**Files:**
- Modify: `charles_mcp/tools/live_tools.py`
- Modify: `charles_mcp/live_state.py`
- Modify: `charles_mcp/client.py`
- Test: `tests/test_live_capture_lifecycle.py`

**Step 1: Write the failing test**

```python
async def test_stop_live_capture_persists_snapshot():
    ...


async def test_peek_live_capture_does_not_advance_cursor():
    ...
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_live_capture_lifecycle.py -q`
Expected: FAIL because lifecycle tools are incomplete

**Step 3: Write minimal implementation**

```python
@mcp.tool()
async def start_live_capture(reset_session: bool = True) -> LiveCaptureStatus: ...

@mcp.tool()
async def peek_live_capture(capture_id: str, cursor: int | None = None) -> LiveCaptureReadResult: ...

@mcp.tool()
async def stop_live_capture(capture_id: str, persist: bool = True) -> StopLiveCaptureResult: ...
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_live_capture_lifecycle.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/tools/live_tools.py charles_mcp/live_state.py charles_mcp/client.py tests/test_live_capture_lifecycle.py
git commit -m "feat: add live capture lifecycle tools and session isolation"
```

### Task 6: 重命名并收敛历史查询工具

**Files:**
- Modify: `charles_mcp/tools/history_tools.py`
- Modify: `README.md`
- Create: `docs/contracts/live-capture.md`
- Test: `tests/test_tool_names_and_docs.py`

**Step 1: Write the failing test**

```python
def test_tool_names_distinguish_live_and_history_paths():
    ...
    assert "start_live_capture" in names
    assert "query_recorded_traffic" in names
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_tool_names_and_docs.py -q`
Expected: FAIL because current names still blur the semantics

**Step 3: Write minimal implementation**

```python
start_live_capture
read_live_capture
peek_live_capture
stop_live_capture
query_recorded_traffic
list_recordings
get_recording_snapshot
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_tool_names_and_docs.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/tools/history_tools.py README.md docs/contracts/live-capture.md tests/test_tool_names_and_docs.py
git commit -m "refactor: rename tools to separate live capture from recording history"
```
