# Tool Contract

本文档定义 Charles MCP 的 **canonical public surface** 与逐工具契约。
默认 `create_server()` 只公开本文档声明的 canonical 工具。
legacy compatibility tools 不属于默认公开工具面，仅在显式兼容模式下暴露。

安装、环境变量和 Claude CLI / Codex CLI / Antigravity 配置示例请看：

- [README.md](../../README.md)
- [README.en.md](../../README.en.md)
- [docs/README.md](../README.md)
- [AGENTS.md](../../AGENTS.md)
- [agent-workflows.md](../agent-workflows.md)
- [legacy-tools migration](../migrations/legacy-tools.md)

默认假设与 README 保持一致：

- `CHARLES_USER=admin`
- `CHARLES_PASS=123456`
- `CHARLES_MANAGE_LIFECYCLE=false`

## 总体规则

1. live 与 history 是两条独立链路，不要混用 source identity。
2. 先 group 或 summary，再 detail。
3. 默认把 summary 当作主数据源，不要一上来拉 full body。
4. `include_sensitive` 仅为兼容保留，不再影响输出。
5. 只有 `stop_live_capture.status="stopped"` 才表示真正关闭完成。
6. 输出已做序列化瘦身：`header_map`、`parsed_json`、`parsed_form`、`lower_name` 不在输出中；`null` 值自动剥离。

## Canonical Surface (Parseable)

<!-- CANONICAL_PUBLIC_SURFACE:START -->
```json
{
  "canonical_public_tool_names": [
    "start_live_capture",
    "read_live_capture",
    "peek_live_capture",
    "stop_live_capture",
    "query_live_capture_entries",
    "list_recordings",
    "get_recording_snapshot",
    "query_recorded_traffic",
    "analyze_recorded_traffic",
    "group_capture_analysis",
    "get_capture_analysis_stats",
    "get_traffic_entry_detail",
    "charles_status",
    "throttling",
    "reset_environment",
    "reverse_import_session",
    "reverse_list_captures",
    "reverse_query_entries",
    "reverse_get_entry_detail",
    "reverse_decode_entry_body",
    "reverse_replay_entry",
    "reverse_discover_signature_candidates",
    "reverse_list_findings",
    "reverse_start_live_analysis",
    "reverse_peek_live_entries",
    "reverse_read_live_entries",
    "reverse_stop_live_analysis",
    "reverse_charles_recording_status",
    "reverse_analyze_live_login_flow",
    "reverse_analyze_live_api_flow",
    "reverse_analyze_live_signature_flow"
  ],
  "legacy_compat_tool_names": [
    "filter_func",
    "proxy_by_time",
    "list_sessions"
  ]
}
```
<!-- CANONICAL_PUBLIC_SURFACE:END -->

## 推荐工具范围

本文档只覆盖 canonical public tools。兼容保留入口不在这里展开。

### Live capture tools

| 工具 | 核心契约 |
| --- | --- |
| `start_live_capture` | 返回新的或已接管的 `capture_id`，后续 live 工具都依赖它 |
| `read_live_capture` | 基于 `capture_id + cursor` 增量读取，并推进 cursor |
| `peek_live_capture` | 基于 `capture_id + cursor` 预览新增项，但不推进 cursor |
| `stop_live_capture` | 结束 capture，必要时持久化；返回 `status`、`recoverable`、`active_capture_preserved` |
| `query_live_capture_entries` | 基于 live capture 输出结构化 summary，并返回 `next_cursor` |

### History tools

| 工具 | 核心契约 |
| --- | --- |
| `list_recordings` | 返回可用录包列表 |
| `get_recording_snapshot` | 返回某个录包的原始快照内容 |
| `query_recorded_traffic` | 对最新保存录包做轻量过滤查询 |
| `analyze_recorded_traffic` | 对指定录包或最新录包返回结构化 summary |

### Shared analysis tools

| 工具 | 核心契约 |
| --- | --- |
| `group_capture_analysis` | 按 `host`、`path`、`status` 等维度做聚合，适合先看热点 |
| `get_capture_analysis_stats` | 返回分类计数和总量统计 |
| `get_traffic_entry_detail` | 只读取单条 `entry_id` 的 detail，不用于批量明细拉取 |

### Status and control tools

| 工具 | 核心契约 |
| --- | --- |
| `charles_status` | 返回 Charles 连通性与 active capture 状态 |
| `throttling` | 设置 Charles 弱网预设 |
| `reset_environment` | 恢复 Charles 配置并清理运行环境 |

### Reverse analysis tools

| 工具 | 核心契约 |
| --- | --- |
| `reverse_import_session` | 导入官方 Charles XML / native session，返回 `capture_id` 供后续 reverse 查询与回放使用 |
| `reverse_list_captures` | 返回 reverse SQLite 中已导入的数据集列表 |
| `reverse_query_entries` | 只按 route 级字段筛选已导入 reverse entry，不展开 detail |
| `reverse_get_entry_detail` | 读取单条 reverse entry 的 canonical detail，包含 request / response / body blob / decoded artifact |
| `reverse_decode_entry_body` | 对单条 reverse entry 的 request / response body 做结构化解码 |
| `reverse_replay_entry` | 对单条 reverse entry 做 replay，必要时保存 experiment / run / finding |
| `reverse_discover_signature_candidates` | 对多条 reverse entry 做字段对比并输出疑似签名参数排名 |
| `reverse_list_findings` | 返回 reverse replay / signature 相关 finding |
| `reverse_start_live_analysis` | 启动 reverse live session，后续 reverse live 工具依赖 `live_session_id` |
| `reverse_peek_live_entries` | 读取 reverse live session 的新增流量，但不推进 cursor |
| `reverse_read_live_entries` | 读取并推进 reverse live session 的 cursor |
| `reverse_stop_live_analysis` | 停止 reverse live session，并按参数决定是否恢复录制状态 |
| `reverse_charles_recording_status` | 同时返回 Charles 录制状态和 reverse live session 状态 |
| `reverse_analyze_live_login_flow` | 在 reverse live 流量上执行登录 / 鉴权定向工作流 |
| `reverse_analyze_live_api_flow` | 在 reverse live 流量上执行 API 定向工作流 |
| `reverse_analyze_live_signature_flow` | 在 reverse live 流量上执行签名 / 动态参数定向工作流 |

## 推荐调用顺序

### Live

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

原因：

- `group_capture_analysis` 最省 token，适合先定位热点
- `query_live_capture_entries` 返回结构化 summary，适合持续筛选
- `get_traffic_entry_detail` 只在确认目标后使用

### History

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

## Summary-first 约定

### `query_live_capture_entries`

关注这些字段：

- `items`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `next_cursor`
- `warnings`

### `analyze_recorded_traffic`

关注这些字段：

- `items`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `warnings`

### `group_capture_analysis`

支持的常用分组：

- `host`
- `path`
- `response_status`
- `resource_class`
- `method`
- `host_path`
- `host_status`

关注这些字段：

- `groups`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `warnings`

## Data visibility contract

当前实现默认返回原始内容：

- summary / detail / live / history 都不再做脱敏
- `include_sensitive=true/false/不传` 应返回一致结果
- 如果上层需要 masking，应由 MCP 客户端或 agent 自行处理

## Detail contract

### `get_traffic_entry_detail`

规则：

1. 先通过 summary 或 group 确定 `entry_id`
2. history 场景使用 `recording_path`
3. live 场景使用 `capture_id`
4. 没有明确必要时，不要默认 `include_full_body=true`

默认参数（已针对 token 预算优化）：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `include_full_body` | `false` | 是否包含完整 body |
| `max_body_chars` | `2048` | full_text 最大字符数 |

输出序列化规则：

- `header_map` 不出现在输出中（仅用于内部匹配），请从 `headers` 列表获取请求头信息
- `parsed_json`、`parsed_form` 不出现在输出中（由 `full_text` 或 `preview_text` 覆盖）
- `full_text` 存在时，冗余的 `preview_text` 会被自动移除
- 所有值为 `null` 的字段在输出中被自动剥离
- 输出超过 12,000 字符时，`warnings` 中会提示缩小请求范围

history detail 绑定规则：

- history summary 会返回 `recording_path`
- live summary 会返回 `capture_id`
- history detail 缺少 source identity 时必须报错
- 不再静默回退到 latest recording

## `stop_live_capture` contract

### 成功态

```json
{
  "status": "stopped",
  "recoverable": false,
  "active_capture_preserved": false
}
```

含义：

- stop 成功
- active capture 已关闭

### 可恢复失败态

```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

含义：

- 一次短重试后仍失败
- capture 仍被保留
- 之后仍可继续 `read_live_capture`
- 也可再次调用 `stop_live_capture`

agent 在 `stop_failed` 时应当：

1. 保留 `capture_id`
2. 不要假设 capture 已关闭
3. 读取 `error` 和 `warnings`
4. 必要时调用 `charles_status`
5. 需要继续收尾时，再次调用 `stop_live_capture`

相关 warning：

- `stop_recording_retry_succeeded`
- `stop_recording_failed_after_retry`
