# Charles MCP Stabilization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复当前 Charles MCP server 的高风险缺陷，并把工具契约、配置、测试和文档整理成可持续演进的工程形态。

**Architecture:** 先修复入口、生命周期和错误模型这类会直接影响可用性与安全性的缺陷；随后把配置、tool schema、运行时目录和日志抽成稳定边界；最后补齐测试、CI 和文档，把当前“单文件式 server”演进成“入口层 + tool 层 + adapter 层 + schema 层”的结构。新方案继续基于 FastMCP，但只使用公开 API，并为只读查询预留 resource 边界。

**Tech Stack:** Python 3.10+, MCP Python SDK (FastMCP), Pydantic v2, httpx, pytest, pytest-asyncio, Ruff, mypy

---

### Task 1: 修复启动入口与生命周期注册

**Files:**
- Create: `charles_mcp/main.py`
- Modify: `charles_mcp/server.py`
- Modify: `charles-mcp-server.py`
- Modify: `pyproject.toml`
- Test: `tests/test_server_bootstrap.py`

**Step 1: Write the failing test**

```python
from charles_mcp.server import create_server
import charles_mcp.main as main_module


def test_console_entry_exists():
    assert callable(main_module.main)


def test_server_registers_public_lifespan():
    server = create_server()
    assert server.settings.lifespan is not None
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_server_bootstrap.py -q`
Expected: FAIL because `charles_mcp.main` does not exist and `server.settings.lifespan` is `None`

**Step 3: Write minimal implementation**

```python
# charles_mcp/main.py
from charles_mcp.server import create_server
from charles_mcp.utils import setup_logging, setup_windows_stdio


def main() -> None:
    setup_logging()
    setup_windows_stdio()
    create_server().run(transport="stdio")
```

```python
# charles_mcp/server.py
mcp = FastMCP(
    "CharlesMCP",
    json_response=True,
    lifespan=lifespan,
)
```

```toml
[project.scripts]
charles-mcp = "charles_mcp.main:main"
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_server_bootstrap.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/main.py charles_mcp/server.py charles-mcp-server.py pyproject.toml tests/test_server_bootstrap.py
git commit -m "fix: restore valid startup entry and FastMCP lifespan registration"
```

### Task 2: 重构配置与运行时目录，消除危险的全局状态和错误备份恢复

**Files:**
- Modify: `charles_mcp/config.py`
- Modify: `charles_mcp/server.py`
- Modify: `charles_mcp/utils.py`
- Test: `tests/test_config_runtime_paths.py`
- Test: `tests/test_restore_guardrails.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from charles_mcp.config import Config


def test_runtime_dirs_are_not_site_package_relative(tmp_path: Path):
    config = Config(runtime_root=str(tmp_path))
    assert config.package_dir == str(tmp_path / "package")
    assert config.backup_dir == str(tmp_path / "backups")


def test_restore_requires_run_scoped_backup(tmp_path: Path):
    config = Config(runtime_root=str(tmp_path))
    assert config.has_valid_backup() is False
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_config_runtime_paths.py tests/test_restore_guardrails.py -q`
Expected: FAIL because config has no `runtime_root` or backup guard

**Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field


class RuntimePaths(BaseModel):
    runtime_root: str
    package_dir: str
    backup_dir: str
```

```python
def has_valid_backup(self) -> bool:
    return Path(self.backup_manifest).exists()
```

```python
if not config.has_valid_backup():
    raise RuntimeError("No run-scoped backup available; refusing to overwrite Charles config")
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_config_runtime_paths.py tests/test_restore_guardrails.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/config.py charles_mcp/server.py charles_mcp/utils.py tests/test_config_runtime_paths.py tests/test_restore_guardrails.py
git commit -m "fix: isolate runtime state and add restore guardrails"
```

### Task 3: 统一 tool 输入输出 schema 与异常模型

**Files:**
- Create: `charles_mcp/schemas.py`
- Create: `charles_mcp/errors.py`
- Modify: `charles_mcp/server.py`
- Modify: `charles_mcp/client.py`
- Test: `tests/test_tool_contracts.py`

**Step 1: Write the failing test**

```python
from charles_mcp.server import create_server


def test_charles_status_has_output_schema():
    server = create_server()
    assert server._tool_manager._tools["charles_status"].output_schema is not None


def test_filter_func_accepts_null_http_method_by_omission_only():
    server = create_server()
    schema = server._tool_manager._tools["filter_func"].parameters
    assert "enum" not in schema["properties"]["http_method"]
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_tool_contracts.py -q`
Expected: FAIL because output schema is missing and `http_method` schema is inconsistent

**Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field


class ToolErrorPayload(BaseModel):
    code: str
    message: str
    retryable: bool = False
    hint: str | None = None


class CharlesStatusResult(BaseModel):
    connected: bool
    config: dict[str, str]
    charles_info: dict[str, str] | None = None
```

```python
from mcp.server.fastmcp.exceptions import ToolError


raise ToolError("Invalid http_method; expected GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS")
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_tool_contracts.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/schemas.py charles_mcp/errors.py charles_mcp/server.py charles_mcp/client.py tests/test_tool_contracts.py
git commit -m "refactor: standardize tool schemas and MCP error handling"
```

### Task 4: 拆分 server 与 Charles adapter，补齐可测性

**Files:**
- Create: `charles_mcp/services/session_service.py`
- Create: `charles_mcp/tools/session_tools.py`
- Create: `charles_mcp/tools/admin_tools.py`
- Modify: `charles_mcp/server.py`
- Modify: `charles_mcp/client.py`
- Test: `tests/test_session_tools.py`
- Test: `tests/test_admin_tools.py`

**Step 1: Write the failing test**

```python
from unittest.mock import AsyncMock


async def test_proxy_by_time_maps_client_errors_to_tool_errors():
    client = AsyncMock()
    client.record_session.side_effect = RuntimeError("boom")
    ...
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_session_tools.py tests/test_admin_tools.py -q`
Expected: FAIL because tool logic is still nested inside `create_server()` and hard to inject

**Step 3: Write minimal implementation**

```python
class SessionService:
    def __init__(self, client_factory):
        self.client_factory = client_factory
```

```python
def register_session_tools(mcp: FastMCP, service: SessionService) -> None:
    ...
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_session_tools.py tests/test_admin_tools.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/services/session_service.py charles_mcp/tools/session_tools.py charles_mcp/tools/admin_tools.py charles_mcp/server.py charles_mcp/client.py tests/test_session_tools.py tests/test_admin_tools.py
git commit -m "refactor: split tool registration from Charles service logic"
```

### Task 5: 加强日志、健康检查和输出裁剪

**Files:**
- Modify: `charles_mcp/utils.py`
- Modify: `charles_mcp/server.py`
- Modify: `charles_mcp/client.py`
- Test: `tests/test_logging_and_limits.py`

**Step 1: Write the failing test**

```python
def test_status_payload_contains_runtime_metadata():
    ...


def test_filter_func_can_truncate_large_payloads():
    ...
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_logging_and_limits.py -q`
Expected: FAIL because there is no standard log context or result truncation

**Step 3: Write minimal implementation**

```python
logger.info(
    "tool_call",
    extra={
        "tool_name": "filter_func",
        "request_id": request_id,
        "duration_ms": duration_ms,
        "result_items": len(items),
    },
)
```

```python
class Pagination(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_logging_and_limits.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add charles_mcp/utils.py charles_mcp/server.py charles_mcp/client.py tests/test_logging_and_limits.py
git commit -m "feat: add structured logging, health details, and payload limits"
```

### Task 6: 补齐工程脚手架、CI 和文档

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `.gitignore`
- Create: `.github/workflows/ci.yml`
- Create: `docs/contracts/tools.md`
- Create: `tests/fixtures/session_sample.chlsj`

**Step 1: Write the failing test**

```python
def test_readme_mentions_console_entry_and_runtime_root():
    ...
```

**Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_docs_smoke.py -q`
Expected: FAIL because docs still describe hard-coded local paths and incorrect lifecycle guarantees

**Step 3: Write minimal implementation**

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e .[dev]
      - run: python -m pytest -q
      - run: python -m ruff check .
```

**Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_docs_smoke.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml README.md .env.example .gitignore .github/workflows/ci.yml docs/contracts/tools.md tests/fixtures/session_sample.chlsj
git commit -m "chore: add CI, fixtures, and accurate operator documentation"
```
