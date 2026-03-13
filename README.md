# Charles MCP Server

[English README](README.en.md) | [Tool Contract](docs/contracts/tools.md)

Charles MCP Server 用于把 Charles Proxy 接入 MCP 客户端，让 agent 可以稳定地读取实时流量、分析历史录包，并在需要时再展开单条请求细节。

它解决的核心问题只有三个：

- 录制还在进行时，agent 也能持续读取当前 session 的增量流量
- live 与 history 统一走结构化分析，不再让 agent 直接消费原始抓包字典
- 默认使用 summary-first 输出，先看热点与摘要，再 drill-down 到单条 detail

## 快速开始

### 1. 开启 Charles Web Interface

在 Charles 中依次进入：`Proxy -> Web Interface Settings`

请确认：

- 勾选 `Enable web interface`
- 用户名为 `admin`
- 密码为 `123456`

菜单位置示意：

![Charles Web Interface Menu](docs/images/charles-web-interface-menu.png)

设置窗口示意：

![Charles Web Interface Settings](docs/images/charles-web-interface-settings.png)

### 2. 安装并配置到 MCP 客户端

无需 clone 仓库，无需手动创建虚拟环境。需要先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

#### Claude Code CLI

```bash
claude mcp add-json charles '{
  "type": "stdio",
  "command": "uvx",
  "args": ["charles-mcp"],
  "env": {
    "CHARLES_USER": "admin",
    "CHARLES_PASS": "123456",
    "CHARLES_MANAGE_LIFECYCLE": "false"
  }
}'
```

#### Claude Desktop / Cursor / 通用 JSON 配置

```json
{
  "mcpServers": {
    "charles": {
      "command": "uvx",
      "args": ["charles-mcp"],
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

#### Codex CLI

```toml
[mcp_servers.charles]
command = "uvx"
args = ["charles-mcp"]

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

### 让 AI 自动安装

将以下提示词复制粘贴给任意 AI agent（Claude Code、ChatGPT、Gemini CLI、Cursor Agent 等），agent 会自动完成安装和配置：

[![自动安装推荐](https://img.shields.io/badge/%E8%87%AA%E5%8A%A8%E5%AE%89%E8%A3%85-%E6%8E%A8%E8%8D%90-e53935?style=for-the-badge)](#让-ai-自动安装)

<details>
<summary><strong>🔴 点击展开自动安装提示词（推荐）</strong></summary>

```text
Install the "charles-mcp" MCP server and configure it for my MCP client. Follow these steps exactly:

Step 1 — Detect OS:
  Determine if this machine runs Windows, macOS, or Linux.

Step 2 — Ensure uv is installed:
  Run: uv --version
  If the command fails (uv not found):
    - macOS/Linux: run: curl -LsSf https://astral.sh/uv/install.sh | sh
    - Windows: run: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  After installing, verify uv works: uv --version

Step 3 — Detect which MCP client is installed:
  Check in this order and use the FIRST match:

  a) Claude Code — run: claude --version
     If it succeeds, run this command and skip to Step 5:
       claude mcp add-json charles '{"type":"stdio","command":"uvx","args":["charles-mcp"],"env":{"CHARLES_USER":"admin","CHARLES_PASS":"123456","CHARLES_MANAGE_LIFECYCLE":"false"}}'

  b) Claude Desktop — check if config file exists:
     - macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json
     - Windows: %APPDATA%\Claude\claude_desktop_config.json
     - Linux:   ~/.config/Claude/claude_desktop_config.json

  c) Cursor — check if any of these exist:
     - ~/.cursor/mcp.json
     - .cursor/mcp.json (in current project)

  d) Windsurf — check if exists:
     - ~/.codeium/windsurf/mcp_config.json

  If none detected, ask the user which client they use.

Step 4 — Write config (for clients b/c/d):
  The config entry to add is:
    "charles": {
      "command": "uvx",
      "args": ["charles-mcp"],
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }

  IMPORTANT: If the config file already exists, read it first, parse the JSON,
  add the "charles" key inside "mcpServers" (create "mcpServers" if absent),
  and write back. Do NOT overwrite other existing MCP server entries.
  If the file does not exist, create it with:
    { "mcpServers": { "charles": { ... } } }

Step 5 — Verify:
  Run: uvx charles-mcp
  Wait 3 seconds then terminate the process.
  If it starts without import errors, the installation is successful.

Step 6 — Report:
  Print: "charles-mcp installed successfully. Please restart your MCP client to load the new server."
  Also mention that Charles Proxy must be running with Web Interface enabled (Proxy → Web Interface Settings, username: admin, password: 123456).
```

</details>

## 前置条件

- Python 3.10+
- 本机已启动 Charles Proxy
- Charles Web Interface 已启用
- Charles 代理默认监听 `127.0.0.1:8888`

推荐默认保持 `CHARLES_MANAGE_LIFECYCLE=false`。除非你明确希望 MCP server 接管 Charles 生命周期，否则不要让它在退出时关闭你的 Charles 进程。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CHARLES_USER` | `admin` | Charles Web Interface 用户名 |
| `CHARLES_PASS` | `123456` | Charles Web Interface 密码 |
| `CHARLES_PROXY_HOST` | `127.0.0.1` | Charles 代理主机 |
| `CHARLES_PROXY_PORT` | `8888` | Charles 代理端口 |
| `CHARLES_CONFIG_PATH` | 自动探测 | Charles 配置文件路径 |
| `CHARLES_REQUEST_TIMEOUT` | `10` | 控制面 HTTP 超时秒数 |
| `CHARLES_MAX_STOPTIME` | `3600` | 有界录制最大时长 |
| `CHARLES_MANAGE_LIFECYCLE` | `false` | 是否由 MCP server 管理 Charles 启停 |

## 推荐使用路径

### 实时分析

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

这条路径的目标是先用最少 token 找到热点，再按需展开单条请求。

### 历史分析

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

这条路径适合先浏览录包，再对结构化 summary 做筛选和 drill-down。

## 当前版本重点变化

- `read_live_capture` 与 `peek_live_capture` 现在只返回路由级摘要字段，例如 `host`、`method`、`path`、`status`，不再直接抛出完整原始 Charles entry，避免在实时轮询时快速打满上下文。
- `query_live_capture_entries` 改为只读分析入口，不会推进 live cursor。你可以基于同一个 `capture_id` 反复换过滤条件查询，而不会把历史增量“消费掉”。
- `analyze_recorded_traffic` 和 `query_live_capture_entries` 的 summary 项会显式返回 `matched_fields` 与 `match_reasons`，便于 agent 解释“为什么这条流量被选中”。
- `get_traffic_entry_detail` 默认 `include_full_body=false`、`max_body_chars=2048`。如果 detail 估算输出超过约 12,000 字符，会在 `warnings` 中提示缩小范围或关闭 full body。
- detail / summary 输出会自动剥离 `null` 值，并隐藏 `header_map`、`parsed_json`、`parsed_form`、`lower_name` 等内部字段；需要查看头信息时请使用 `headers` 列表。

## 工具总览

README 只覆盖推荐使用的主流程工具。兼容保留入口不在本文档中展开。

### Live capture tools

| 工具 | 作用 | 何时使用 |
| --- | --- | --- |
| `start_live_capture` | 启动或接管当前 live capture，并返回 `capture_id` | 开始实时观察前 |
| `read_live_capture` | 按 cursor 增量读取 live capture，并只返回紧凑路由摘要 | 连续消费新增流量、只想先看 host/path/status 时 |
| `peek_live_capture` | 预览新增流量但不推进 cursor，并只返回紧凑路由摘要 | 想先看一眼而不改变读取进度时 |
| `stop_live_capture` | 结束 capture，并在需要时持久化快照 | 收尾或导出本次实时抓包时 |
| `query_live_capture_entries` | 对 live capture 输出结构化 summary，且不推进 cursor | 想从实时流量里反复筛关键请求时 |

### Analysis tools

| 工具 | 作用 | 何时使用 |
| --- | --- | --- |
| `group_capture_analysis` | 对 live 或 history 结果聚合分组 | 先看热点 host、path、status 时 |
| `get_capture_analysis_stats` | 返回分类统计结果 | 想快速知道 API、静态资源、错误流量占比时 |
| `get_traffic_entry_detail` | 读取单条 entry 的 detail，并在响应过大时给出 warnings | 已经拿到目标 `entry_id`，准备 drill-down 时 |
| `analyze_recorded_traffic` | 对指定录包或最新录包输出结构化 summary，并附带匹配原因 | 想分析历史 `.chlsj` 时 |

### History tools

| 工具 | 作用 | 何时使用 |
| --- | --- | --- |
| `list_recordings` | 列出当前已保存的录包文件 | 想先知道有哪些历史录包时 |
| `get_recording_snapshot` | 读取某个录包的原始快照 | 需要完整查看某个保存快照时 |
| `query_recorded_traffic` | 直接对最新录包做轻量过滤 | 需要快速查找 host、method、regex 命中时 |

### Status and control tools

| 工具 | 作用 | 何时使用 |
| --- | --- | --- |
| `charles_status` | 查看 Charles 连接状态与当前 live capture 状态 | 怀疑连接异常或想确认 capture 是否仍在活动时 |
| `throttling` | 设置 Charles 弱网预设 | 需要模拟 3G / 4G / 5G / off 等网络条件时 |
| `reset_environment` | 恢复 Charles 配置并清理当前环境 | 需要回到干净环境时 |

## 关键使用约定

### 1. 默认返回原始数据

所有工具默认返回完整原始内容，不做脱敏处理。如果上层需要 masking，应由 MCP 客户端或 agent 自行处理。

### 2. 先 summary，再 detail

推荐先用 `group_capture_analysis`、`query_live_capture_entries` 或 `analyze_recorded_traffic` 确认目标，再调用 `get_traffic_entry_detail`。

默认不要一开始就请求 `include_full_body=true`。

### 3. 输出已针对 token 预算优化

所有 summary 和 detail 输出都经过了序列化瘦身：

- `header_map`、`parsed_json`、`parsed_form`、`lower_name` 等内部字段不再出现在输出中
- 值为 `null` 的字段在序列化时自动剥离
- detail 视图中 `full_text` 存在时，冗余的 `preview_text` 会被移除

默认参数已调低以保护上下文窗口：

| 参数 | 旧默认 | 新默认 |
| --- | --- | --- |
| `max_items` | 20 | 10 |
| `max_preview_chars` | 256 | 128 |
| `max_headers_per_side` | 8 | 6 |
| `max_body_chars` | 4096 | 2048 |

如需更大范围查看，仍可手动传入更高的值。

### 4. history detail 需要稳定 source identity

history summary 会返回 `recording_path`，live summary 会返回 `capture_id`。

对 `get_traffic_entry_detail`：

- history 场景优先传 `recording_path`
- live 场景优先传 `capture_id`

### 5. `stop_live_capture` 的失败是可恢复的

`stop_live_capture` 有两个稳定结束态：

- `status="stopped"`：真正关闭完成
- `status="stop_failed"`：短重试后仍失败，但 capture 仍保留

当返回 `stop_failed` 时，应同时关注：

- `recoverable`
- `active_capture_preserved`

如果结果是：

```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

说明当前 capture 仍然可继续读取、诊断、再次 stop，而不是已经被关闭。

## 开发

运行测试：

```bash
python -m pytest -q
```

常用本地检查：

```bash
python charles-mcp-server.py
python -c "from charles_mcp.main import main; main()"
```

## 感谢支持

如果这个项目对你有帮助，欢迎请我喝杯咖啡，支持后续维护与迭代。

### 微信赞赏码

![微信赞赏码](docs/images/wechat-donate.png)

### USDT-TRC20

`TCudxn9ByCxPZHXLtvqBjFmLWXywBoicRs`

## 更新日志

### 2026-03-13 (v2)

- **修复 `lower_name` 校验崩溃**：`HeaderKV.lower_name` 添加默认值与自动计算 validator，解决 `get_traffic_entry_detail` 输出校验报错 `'lower_name' is a required property` 导致工具完全不可用的问题
- **修复游标逻辑陷阱**：`query_live_capture_entries` 改为只读分析（不再推进内部 cursor），避免 agent 反复调用后历史数据被"消费"、始终返回空列表的问题
- **防止 Context 爆炸**：`read_live_capture` 和 `peek_live_capture` 返回前自动将原始 entry 压缩为路由摘要（host/method/path/status），不再把完整 HTTP 请求/响应原文直接抛给大模型
- **打破 Agent 死循环**：以上三个修复共同消除了 agent 在实时分析时因 detail 崩溃 → 回退查询 → 游标已过无数据 → 不断重试的死循环模式
- **改善工具描述**：所有 live/history 工具补充了使用指引、副作用说明和推荐调用路径

### 2026-03-13

- **Token 预算优化**：序列化输出瘦身约 50%，解决多次 `get_traffic_entry_detail` 后触发 Context limit reached 的问题
  - `header_map`、`parsed_json`、`parsed_form`、`lower_name` 标记为内部字段，不再出现在工具输出中
  - `TrafficQueryResult` 和 `TrafficDetailResult` 自动剥离 `null` 值
  - detail 视图中 `full_text` 存在时自动去除冗余的 `preview_text`
- **降低默认参数**：`max_items` 20→10、`max_preview_chars` 256→128、`max_headers_per_side` 8→6、`max_body_chars` 4096→2048
- **大响应预警**：`get_traffic_entry_detail` 输出超过 12,000 字符时，在 `warnings` 中提示 agent 缩小请求范围

### 2026-03-11

- **移除已废弃的 redaction 体系**：删除 `include_sensitive` 参数和全部 `redactions_applied` / `redacted` / `sensitive_included` 字段，减少工具签名噪音
- **修复 `errors_only` 预设语义**：该预设现在会自动注入 `has_error=True`，只返回真正出错的流量
- **HTTP 连接复用**：`LiveCaptureService` 在 start → read → stop 全生命周期复用同一 HTTP 连接，减少高频轮询时的 TCP 开销
- **entry_id 计算轻量化**：从 JSON 全序列化改为管道拼接关键字段后 SHA1，避免对大 body 做不必要的序列化

## 另见

- [English README](README.en.md)
- [Tool Contract](docs/contracts/tools.md)
