# Tool Contract

本文档定义 Charles MCP 推荐工具的对外契约，重点面向 agent 如何稳定调用，而不是安装或客户端接入步骤。

安装、环境变量和 Claude CLI / Codex CLI / Antigravity 配置示例请看：

- [README.md](../../README.md)
- [README.en.md](../../README.en.md)

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

## 推荐工具范围

本文档只覆盖推荐使用的主流程工具。兼容保留入口不在这里展开。

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
