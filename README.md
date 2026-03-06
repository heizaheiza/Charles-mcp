# Charles MCP Server

[English README](README.en.md) | [Tool Contract](docs/contracts/tools.md)

Charles Proxy 的 MCP 集成工具，面向 agent 的核心能力包括：

- 读取 Charles 当前 session 的实时增量数据，而不是误读历史 `.chlsj`
- 对 live/history 两条数据通路做统一分析
- 默认优先筛出关键 API 请求，过滤图片、字体、媒体等高噪音资源
- 默认脱敏，避免把 `Authorization`、`Cookie`、token 等敏感数据直接暴露给 agent
- 默认 summary-first，控制 token 消耗，detail drill-down 时再展开完整内容

## 工具亮点

1. 实时抓包可读
- `start_live_capture` / `read_live_capture` / `peek_live_capture` / `stop_live_capture`
- 支持边录边看边分析，不需要等录制结束

2. token 友好的分析输出
- `query_live_capture_entries`
- `analyze_recorded_traffic`
- `group_capture_analysis`
- 默认 `preset="api_focus"`，优先返回 API/JSON 请求
- 默认统计并过滤 `static_asset`、`media`、`font`、`connect_tunnel` 等高噪音资源

3. 结构化 detail drill-down
- `get_traffic_entry_detail`
- 默认返回脱敏后的 detail
- 只有显式请求时才展开更完整的 request/response 细节

4. 更稳的 stop 收尾
- `stop_live_capture` 内部会做一次短重试
- 若两次 stop 都失败，返回 `status="stop_failed"`
- 同时返回 `recoverable=true` 与 `active_capture_preserved=true`
- 这表示 active capture 仍保留，agent 可以继续读取或再次 stop，而不是直接丢状态

## 当前能力概览

当前 server 暴露三组主要能力：

1. Live capture tools
- `start_live_capture`
- `read_live_capture`
- `peek_live_capture`
- `stop_live_capture`
- `query_live_capture_entries`
- `get_capture_analysis_stats`
- `group_capture_analysis`

2. History tools
- `analyze_recorded_traffic`
- `query_recorded_traffic`
- `list_recordings`
- `get_recording_snapshot`
- `get_traffic_entry_detail`

3. Status / control tools
- `charles_status`
- `throttling`
- `reset_environment`

兼容保留但不建议继续用于主路径的 legacy tools：

- `proxy_by_time`
- `filter_func`

## 运行要求

- Python 3.10+
- 本机已启动 Charles Proxy
- Charles Web Interface 已启用
- Charles 代理默认监听 `127.0.0.1:8888`

## 安装

开发环境：

```bash
pip install -e .[dev]
```

安装后的命令入口：

```bash
charles-mcp
```

包入口：

```text
charles_mcp.main:main
```

仓库内兼容入口：

```bash
python charles-mcp-server.py
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CHARLES_USER` | `tower` | Charles Web Interface 用户名 |
| `CHARLES_PASS` | `123456` | Charles Web Interface 密码 |
| `CHARLES_PROXY_HOST` | `127.0.0.1` | Charles 代理主机 |
| `CHARLES_PROXY_PORT` | `8888` | Charles 代理端口 |
| `CHARLES_CONFIG_PATH` | 自动探测 | Charles 配置文件路径 |
| `CHARLES_REQUEST_TIMEOUT` | `10` | 控制面 HTTP 超时秒数 |
| `CHARLES_MAX_STOPTIME` | `3600` | 离线录制最大时长 |
| `CHARLES_MANAGE_LIFECYCLE` | `false` | 是否由 MCP server 在启动/退出时管理 Charles 生命周期 |

`CHARLES_MANAGE_LIFECYCLE=false` 是默认推荐值。默认情况下，MCP server 不应在退出时替用户关闭 Charles 进程。

## 各种终端中的配置方法

### PowerShell

当前会话：

```powershell
$env:CHARLES_USER = "tower"
$env:CHARLES_PASS = "123456"
$env:CHARLES_PROXY_HOST = "127.0.0.1"
$env:CHARLES_PROXY_PORT = "8888"
$env:CHARLES_MANAGE_LIFECYCLE = "false"
charles-mcp
```

### Windows CMD

```cmd
set CHARLES_USER=tower
set CHARLES_PASS=123456
set CHARLES_PROXY_HOST=127.0.0.1
set CHARLES_PROXY_PORT=8888
set CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### Git Bash / Bash / Zsh

```bash
export CHARLES_USER=tower
export CHARLES_PASS=123456
export CHARLES_PROXY_HOST=127.0.0.1
export CHARLES_PROXY_PORT=8888
export CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### 直接用 Python 入口启动

适合不想依赖 console script，或者需要在任意终端里显式指定入口：

```bash
python -c "from charles_mcp.main import main; main()"
```

## 各类 MCP 客户端中的配置方法

### 通用 stdio MCP 配置

适用于支持 `command + args + env` 的 MCP 客户端。

```json
{
  "mcpServers": {
    "charles": {
      "command": "charles-mcp",
      "env": {
        "CHARLES_USER": "tower",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

### Claude Desktop 风格配置

如果客户端允许显式指定 Python 入口，可以这样写：

```json
{
  "mcpServers": {
    "charles": {
      "command": "python",
      "args": ["-c", "from charles_mcp.main import main; main()"],
      "env": {
        "CHARLES_USER": "tower",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

### 仓库本地开发配置

适合直接在仓库里运行：

```json
{
  "mcpServers": {
    "charles": {
      "command": "python",
      "args": ["charles-mcp-server.py"],
      "cwd": "E:/project/Charles-mcp",
      "env": {
        "CHARLES_USER": "tower",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

## 推荐使用方式

### 实时分析主路径

推荐给 agent 的调用顺序：

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

原因：
- `group_capture_analysis` 先给热点分组，最省 token
- `query_live_capture_entries` 再拿结构化 summary
- `get_traffic_entry_detail` 只在确认某条请求值得看时再展开

### 历史分析主路径

推荐顺序：

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

## Agent 调用规范

### 1. 默认先走分组，再走 summary，再 drill-down

不推荐一开始就直接拉大批量 detail。推荐顺序：

1. `group_capture_analysis`
2. `query_live_capture_entries` 或 `analyze_recorded_traffic`
3. `get_traffic_entry_detail`

### 2. 默认使用 `preset="api_focus"`

这个 preset 会优先保留：
- JSON / API / GraphQL / Auth 请求
- 高优先级的变更型方法：`POST`、`PUT`、`PATCH`、`DELETE`
- 错误请求

并默认过滤或降权：
- `control.charles`
- `CONNECT`
- 图片
- 字体
- 媒体
- 大量静态资源

### 3. 默认把 summary 当作主数据源

summary 返回的是 agent 友好的低 token 视图，包含：
- method / host / path / status
- content-type
- 关键 header 摘要
- request/response body preview
- `matched_fields`
- `match_reasons`
- `redactions_applied`
- `filtered_out_by_class`

### 4. 只有明确需要时再看 detail

只有当某条 entry 已经被确认值得深挖时，才调用：
- `get_traffic_entry_detail`

如果没有明确需要，不要默认拉 `include_full_body=true`。

## `stop_failed + recoverable=true` 的处理规范

`stop_live_capture` 现在有两种稳定状态：

1. `status="stopped"`
- 说明 stop 成功
- active capture 已清理
- 如果 `persist=true`，可能返回 `persisted_path`

2. `status="stop_failed"`
- 说明 stop 在一次短重试后仍失败
- 这不是“会话已经结束”的同义词
- 必须结合下面两个字段解释：
  - `recoverable=true`
  - `active_capture_preserved=true`

### agent 必须如何处理 `stop_failed`

当返回：

```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

agent 的正确处理方式是：

1. 不要丢弃 `capture_id`
2. 不要假设 Charles 已经停止录制
3. 读取 `error` 与 `warnings`
4. 如需确认当前状态，先调用 `charles_status`
5. 如需确认数据是否仍可读，可继续调用 `read_live_capture`
6. 如需继续收尾，应再次调用 `stop_live_capture`
7. 只有在 `status="stopped"` 时，才把该 capture 视为真正关闭

### `stop_live_capture` 的恢复语义

- 内部会做一次短重试
- 如果第二次成功：
  - 返回 `status="stopped"`
  - `warnings` 里可能包含 `stop_recording_retry_succeeded`
- 如果两次都失败：
  - 返回 `status="stop_failed"`
  - `recoverable=true`
  - `active_capture_preserved=true`
  - `warnings` 里包含 `stop_recording_failed_after_retry`

这条契约的目的，是让 agent 能在控制面瞬时失败时继续恢复，而不是直接把 live capture 状态丢掉。

## 主要工具说明

### `start_live_capture`

用途：
- 启动一个新的 live capture
- 或接管当前已在录制的 Charles session

常用参数：
- `reset_session`
- `include_existing`
- `adopt_existing`

### `read_live_capture`

用途：
- 读取当前 live capture 的增量数据

返回关键字段：
- `capture_id`
- `status`
- `items`
- `next_cursor`
- `total_new_items`
- `truncated`
- `warnings`

### `query_live_capture_entries`

用途：
- 对 live capture 做结构化分析查询
- 默认更适合 agent 消费

支持重点参数：
- `preset`
- `method_in`
- `status_in`
- `resource_class_in`
- `request_content_type`
- `response_content_type`
- `request_json_query`
- `response_json_query`

### `group_capture_analysis`

用途：
- 对 live 或 history 数据做低 token 聚合分析
- 适合先看热点 host/path/status 再决定 drill-down

支持分组字段：
- `host`
- `path`
- `response_status`
- `resource_class`
- `method`
- `host_path`
- `host_status`

### `analyze_recorded_traffic`

用途：
- 对历史 `.chlsj` 录制结果做结构化分析

### `get_traffic_entry_detail`

用途：
- 查看单条请求的 detail
- 默认仍然脱敏

建议：
- 没有必要时不要默认 `include_sensitive=true`
- 没有必要时不要默认 `include_full_body=true`

## 安全与默认脱敏

默认会脱敏的敏感字段包括但不限于：

- `Authorization`
- `Proxy-Authorization`
- `Cookie`
- `Set-Cookie`
- `X-Api-Key`
- `token`
- `access_token`
- `refresh_token`
- `session`
- `password`
- `secret`

summary 视图始终应该被视为脱敏视图。

## 不推荐继续扩展的旧工具

以下工具保留兼容，但不应继续作为主路径使用：

- `proxy_by_time`
- `filter_func`

原因：
- 它们不适合作为新的分析能力入口
- 新的 live/history 分析能力已经由结构化 tools 替代

## 开发与验证

运行测试：

```bash
python -m pytest -q
```

常用本地检查：

```bash
python charles-mcp-server.py
python -c "from charles_mcp.main import main; main()"
```

更多工具契约与 agent 调用约定见：
- [docs/contracts/tools.md](docs/contracts/tools.md)
- [README.en.md](README.en.md)
