# Tool Contract

本文档定义当前 Charles MCP 工具面向 agent 的推荐调用契约，重点覆盖：

- live/history 主路径
- summary-first 调用方式
- `stop_failed + recoverable=true` 的恢复语义
- 默认 token 控制与预过滤策略

## 1. 总体原则

1. 先分组，再 summary，再 detail
2. 默认使用 `preset="api_focus"`
3. 默认把 summary 视为主数据源
4. detail 只在 drill-down 时才使用
5. `stop_live_capture` 只有在 `status="stopped"` 时才视为真正关闭 capture

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
- legacy tools 仅保留兼容，不应再作为新的分析主入口。

## 3. 推荐的 live 调用顺序

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

为什么这么做：
- `group_capture_analysis` 最省 token，适合先识别热点 host/path/status
- `query_live_capture_entries` 返回结构化 summary，适合 agent 持续筛选
- `get_traffic_entry_detail` 只在确认目标条目后再展开完整细节

## 4. 推荐的 history 调用顺序

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

## 5. summary-first 契约

### `query_live_capture_entries`

适用：
- 当前 live capture 的结构化分析

返回重点：
- `items`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `next_cursor`
- `warnings`

### `analyze_recorded_traffic`

适用：
- 历史 `.chlsj` 快照的结构化分析

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

## 6. token 优化契约

分析类 tools 默认会优先过滤：
- `control.charles`
- `CONNECT`
- `static_asset`
- `media`
- `font`
- 其他高噪音低价值请求

默认推荐：
- `preset="api_focus"`
- 保持较小的 `max_items`
- 不要默认请求 full body
- 先看 `group_capture_analysis`
- 再看 `query_live_capture_entries`

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
- 这不是“会话已经结束”的同义词
- active capture 仍保留
- 之后仍可：
  - `read_live_capture`
  - `peek_live_capture`
  - 再次调用 `stop_live_capture`

### agent 在 `stop_failed` 时必须遵守的规则

1. 保留 `capture_id`
2. 不要假设当前 capture 已关闭
3. 读取 `error` 字段排查失败原因
4. 检查 `warnings`
5. 如有必要，调用 `charles_status`
6. 如还需读取数据，继续 `read_live_capture`
7. 需要收尾时，重试 `stop_live_capture`
8. 只有在 `status="stopped"` 时，才视为关闭完成

### warning 语义

- `stop_recording_retry_succeeded`
  - 第一次 stop 失败，短重试后成功
- `stop_recording_failed_after_retry`
  - 两次 stop 都失败，进入可恢复失败态

## 8. 安全与脱敏契约

默认应视为脱敏输出。

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
- summary 输出应始终视为脱敏视图
- detail 默认也应是脱敏视图
- 只有明确需要时才应请求更完整的 detail

## 9. detail drill-down 契约

### `get_traffic_entry_detail`

推荐用途：
- 对单条 entry 做精细分析
- 不用于批量拉全量 body

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
- `CHARLES_MANAGE_LIFECYCLE=false`

原因：
- MCP server 默认不应在退出时替用户关闭 Charles 进程

## 11. 终端与客户端配置建议

### PowerShell

```powershell
$env:CHARLES_USER = "tower"
$env:CHARLES_PASS = "123456"
$env:CHARLES_MANAGE_LIFECYCLE = "false"
charles-mcp
```

### Windows CMD

```cmd
set CHARLES_USER=tower
set CHARLES_PASS=123456
set CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### Bash / Zsh / Git Bash

```bash
export CHARLES_USER=tower
export CHARLES_PASS=123456
export CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### 通用 MCP stdio 配置

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
