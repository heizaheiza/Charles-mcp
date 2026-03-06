# Tool Contract

本文档定义 Charles MCP 工具的对外契约，重点面向 agent 调用与 MCP 客户端接入，而不是实现细节。

目标：

- 明确 live / history / control 三类能力的边界
- 统一 summary-first 的调用方式，降低 token 消耗
- 说明 `stop_failed + recoverable=true` 的处理规范
- 约束默认脱敏、安全边界和推荐入口

## 1. 总体原则

1. 先 group，再 summary，再 detail
2. 默认使用 `preset="api_focus"`
3. 默认把 summary 当作主数据源
4. detail 只在 drill-down 时使用
5. 只有 `stop_live_capture.status="stopped"` 才视为真正关闭 capture
6. 不要再把 legacy 工具作为新的主流程入口

## 2. 工具分组

### Live capture tools
- `start_live_capture`
- `read_live_capture`
- `peek_live_capture`
- `stop_live_capture`
- `query_live_capture_entries`
- `get_capture_analysis_stats`
- `group_capture_analysis`

### History tools
- `analyze_recorded_traffic`
- `query_recorded_traffic`
- `list_recordings`
- `get_recording_snapshot`
- `get_traffic_entry_detail`

### Status / control tools
- `charles_status`
- `throttling`
- `reset_environment`

### Deprecated tools
- `proxy_by_time`
- `filter_func`

说明：
- deprecated tools 仅保留兼容，不应再扩参数，也不应继续作为新的 agent 主路径。

## 3. 推荐的 live 调用顺序

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

为什么这样设计：
- `group_capture_analysis` 最省 token，适合先定位热点 `host/path/status`
- `query_live_capture_entries` 返回结构化 summary，适合 agent 持续筛选
- `get_traffic_entry_detail` 只在确认目标条目后再展开 detail

## 4. 推荐的 history 调用顺序

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

## 5. summary-first 契约

### `query_live_capture_entries`

适用：
- 对当前 live capture 做结构化分析

返回重点：
- `items`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `next_cursor`
- `warnings`

### `analyze_recorded_traffic`

适用：
- 对历史 `.chlsj` 记录做结构化分析

返回重点：
- `items`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `warnings`

### `group_capture_analysis`

适用：
- 低 token 聚合分析

支持分组字段：
- `host`
- `path`
- `response_status`
- `resource_class`
- `method`
- `host_path`
- `host_status`

返回重点：
- `groups`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `warnings`

## 6. token 优化约束

分析类 tools 默认会优先过滤：
- `control.charles`
- `CONNECT`
- `static_asset`
- `media`
- `font`
- 其他高噪音低价值请求

默认建议：
- `preset="api_focus"`
- 保持较小的 `max_items`
- 不要默认请求 `include_full_body=true`
- 先使用 `group_capture_analysis`
- 再使用 `query_live_capture_entries`

如果结果被裁剪，agent 应结合：
- `truncated`
- `filtered_out_count`
- `filtered_out_by_class`

## 7. `stop_live_capture` 契约

### 成功态

```json
{
  "status": "stopped",
  "recoverable": false,
  "active_capture_preserved": false
}
```

含义：
- Charles stop 成功
- active capture 已从 server 状态中清理
- 该 capture 可以视为关闭

### 可恢复失败态

```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

含义：
- stop 在一次短重试后仍失败
- 这不是“capture 已结束”的同义词
- active capture 仍保留
- 之后仍可：
  - `read_live_capture`
  - `peek_live_capture`
  - 再次调用 `stop_live_capture`

### agent 在 `stop_failed` 时必须遵守的规则

1. 保留 `capture_id`
2. 不要假设当前 capture 已关闭
3. 读取 `error` 字段定位失败原因
4. 检查 `warnings`
5. 必要时调用 `charles_status`
6. 如还需读取数据，继续 `read_live_capture`
7. 需要收尾时，重试 `stop_live_capture`
8. 只有在 `status="stopped"` 时，才视为关闭完成

### warning 语义

- `stop_recording_retry_succeeded`
  - 第一次 stop 失败，短重试后成功
- `stop_recording_failed_after_retry`
  - 两次 stop 都失败，进入可恢复失败态

## 8. 安全与脱敏契约

默认输出应视为脱敏结果。

默认脱敏字段包括但不限于：
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

说明：
- summary 输出始终应视为脱敏视图
- detail 默认也应是脱敏视图
- 只有在明确需要时，才应请求更完整的 detail

## 9. detail drill-down 契约

### `get_traffic_entry_detail`

推荐用途：
- 对单条 entry 做精细分析
- 不用于批量拉取完整 body

推荐规则：
1. 先通过 summary 或 group 确定 `entry_id`
2. 再调用 `get_traffic_entry_detail`
3. 没有明确必要时，不要默认 `include_full_body=true`
4. 没有明确必要时，不要默认 `include_sensitive=true`

## 10. 配置与入口

推荐入口：
- `charles-mcp`
- `python -c "from charles_mcp.main import main; main()"`

核心环境变量：
- `CHARLES_USER`
- `CHARLES_PASS`
- `CHARLES_PROXY_HOST`
- `CHARLES_PROXY_PORT`
- `CHARLES_MANAGE_LIFECYCLE`

推荐默认：
- `CHARLES_USER=admin`
- `CHARLES_PASS=123456`
- `CHARLES_MANAGE_LIFECYCLE=false`

原因：
- MCP server 默认不应在退出时替用户关闭 Charles 进程
- Web Interface 默认账号应和 README 示例保持一致

## 11. 终端与客户端配置建议

### PowerShell

```powershell
$env:CHARLES_USER = "admin"
$env:CHARLES_PASS = "123456"
$env:CHARLES_MANAGE_LIFECYCLE = "false"
charles-mcp
```

### Windows CMD

```cmd
set CHARLES_USER=admin
set CHARLES_PASS=123456
set CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### Bash / Zsh / Git Bash

```bash
export CHARLES_USER=admin
export CHARLES_PASS=123456
export CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### Claude CLI

```bash
claude mcp add-json charles '{
  "type": "stdio",
  "command": "charles-mcp",
  "env": {
    "CHARLES_USER": "admin",
    "CHARLES_PASS": "123456",
    "CHARLES_MANAGE_LIFECYCLE": "false"
  }
}'
```

仓库本地开发：

```bash
claude mcp add-json charles '{
  "type": "stdio",
  "command": "python",
  "args": ["~/Charles-mcp/charles-mcp-server.py"],
  "env": {
    "CHARLES_USER": "admin",
    "CHARLES_PASS": "123456",
    "CHARLES_MANAGE_LIFECYCLE": "false"
  }
}'
```

### Codex CLI

```toml
[mcp_servers.charles]
command = "charles-mcp"

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

仓库本地开发：

```toml
[mcp_servers.charles]
command = "python"
args = ["~/Charles-mcp/charles-mcp-server.py"]

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

### Antigravity

```json
{
  "mcpServers": {
    "charles": {
      "command": "charles-mcp",
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

仓库本地开发：

```json
{
  "mcpServers": {
    "charles": {
      "command": "python",
      "args": ["~/Charles-mcp/charles-mcp-server.py"],
      "cwd": "~/Charles-mcp",
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```
