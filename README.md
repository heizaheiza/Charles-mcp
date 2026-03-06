# Charles MCP Server

[English README](README.en.md) | [Tool Contract](docs/contracts/tools.md)

Charles MCP Server 用于把 Charles Proxy 接入 MCP 客户端，面向 agent 的重点能力是实时抓包、结构化分析、默认脱敏，以及低 token 成本的分层查看。

核心能力：

- 在 Charles 正在录制时读取当前 session 的增量数据，而不是误读历史 `.chlsj`
- 把 live 和 history 两条数据链路分开，避免语义混淆
- 默认优先保留高价值 API 请求，过滤图片、字体、媒体、隧道等高噪音流量
- 默认对 token、cookie、授权头等敏感字段做 redaction
- 默认使用 summary-first 输出，降低 agent 的 token 消耗，只有在需要时才 drill-down 到 detail

## 工具亮点

1. 实时抓包可读
- `start_live_capture`
- `read_live_capture`
- `peek_live_capture`
- `stop_live_capture`

2. 面向 token 优化的数据分析
- `query_live_capture_entries`
- `analyze_recorded_traffic`
- `group_capture_analysis`
- 默认 `preset="api_focus"`
- 默认过滤 `static_asset`、`media`、`font`、`connect_tunnel` 等低价值流量

3. 结构化 drill-down
- `get_traffic_entry_detail`
- detail 默认仍是脱敏视图
- 只有显式请求时才展开更完整的 request/response body

4. 更稳的 stop 收尾语义
- `stop_live_capture` 内部会做一次短重试
- 两次 stop 都失败时返回 `status="stop_failed"`
- 同时返回 `recoverable=true` 与 `active_capture_preserved=true`
- 这表示当前 active capture 仍保留，agent 可以继续读取或再次 stop，而不是直接丢失状态

## 运行要求

- Python 3.10+
- 本机已启动 Charles Proxy
- Charles Web Interface 已启用
- Charles 代理默认监听 `127.0.0.1:8888`

## 安装

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
| `CHARLES_USER` | `admin` | Charles Web Interface 用户名 |
| `CHARLES_PASS` | `123456` | Charles Web Interface 密码 |
| `CHARLES_PROXY_HOST` | `127.0.0.1` | Charles 代理主机 |
| `CHARLES_PROXY_PORT` | `8888` | Charles 代理端口 |
| `CHARLES_CONFIG_PATH` | 自动探测 | Charles 配置文件路径 |
| `CHARLES_REQUEST_TIMEOUT` | `10` | 控制面 HTTP 超时秒数 |
| `CHARLES_MAX_STOPTIME` | `3600` | 有界录制的最大时长 |
| `CHARLES_MANAGE_LIFECYCLE` | `false` | 是否由 MCP server 管理 Charles 启动和退出 |

推荐默认值是 `CHARLES_MANAGE_LIFECYCLE=false`。除非你明确希望 MCP server 接管 Charles 生命周期，否则不要让它在退出时关闭用户自己的 Charles 进程。

## 各种终端中的配置方法

### PowerShell

```powershell
$env:CHARLES_USER = "admin"
$env:CHARLES_PASS = "123456"
$env:CHARLES_PROXY_HOST = "127.0.0.1"
$env:CHARLES_PROXY_PORT = "8888"
$env:CHARLES_MANAGE_LIFECYCLE = "false"
charles-mcp
```

### Windows CMD

```cmd
set CHARLES_USER=admin
set CHARLES_PASS=123456
set CHARLES_PROXY_HOST=127.0.0.1
set CHARLES_PROXY_PORT=8888
set CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### Git Bash / Bash / Zsh

```bash
export CHARLES_USER=admin
export CHARLES_PASS=123456
export CHARLES_PROXY_HOST=127.0.0.1
export CHARLES_PROXY_PORT=8888
export CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

### 直接使用 Python 入口

```bash
python -c "from charles_mcp.main import main; main()"
```

## MCP 客户端配置示例

### 通用 stdio MCP 配置

适用于支持 `command + args + env` 的 MCP 客户端。

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

### Claude CLI

使用 `claude mcp add-json` 添加 stdio MCP server：

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

仓库本地开发配置：

```bash
claude mcp add-json charles '{
  "type": "stdio",
  "command": "python",
  "args": ["E:/project/Charles-mcp/charles-mcp-server.py"],
  "env": {
    "CHARLES_USER": "admin",
    "CHARLES_PASS": "123456",
    "CHARLES_MANAGE_LIFECYCLE": "false"
  }
}'
```

检查当前配置：

```bash
claude mcp get charles
```

### Codex CLI

Codex CLI 从 `~/.codex/config.toml` 读取 MCP server 配置。推荐写法：

```toml
[mcp_servers.charles]
command = "charles-mcp"

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

仓库本地开发写法：

```toml
[mcp_servers.charles]
command = "python"
args = ["E:/project/Charles-mcp/charles-mcp-server.py"]

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

### Antigravity

Antigravity 支持在 `Manage MCP Servers` 或 `View raw config` 中直接编辑 `mcpServers` JSON：

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

仓库本地开发写法：

```json
{
  "mcpServers": {
    "charles": {
      "command": "python",
      "args": ["E:/project/Charles-mcp/charles-mcp-server.py"],
      "cwd": "E:/project/Charles-mcp",
      "env": {
        "CHARLES_USER": "admin",
        "CHARLES_PASS": "123456",
        "CHARLES_MANAGE_LIFECYCLE": "false"
      }
    }
  }
}
```

## 推荐调用路径

### 实时分析路径

推荐给 agent 的调用顺序：

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

原因：
- `group_capture_analysis` 最省 token，适合先看热点 host/path/status
- `query_live_capture_entries` 返回结构化 summary，适合持续筛选
- `get_traffic_entry_detail` 只在确认目标条目后再展开完整细节

### 历史分析路径

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

## Agent 对 `stop_failed + recoverable=true` 的处理规范

`stop_live_capture` 有两个稳定结束态：

1. `status="stopped"`
- stop 成功
- active capture 已关闭
- 当 `persist=true` 时可能返回 `persisted_path`

2. `status="stop_failed"`
- 一次短重试后仍失败
- 这不代表 live capture 已经关闭
- 需要和这两个字段一起解释：
  - `recoverable=true`
  - `active_capture_preserved=true`

当工具返回：

```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

agent 应该：

1. 保留 `capture_id`
2. 不要假设 Charles 已经停止录制
3. 检查 `error` 和 `warnings`
4. 如有必要，调用 `charles_status` 确认当前状态
5. 如果还要继续观察流量，继续调用 `read_live_capture`
6. 如果要继续收尾，再次调用 `stop_live_capture`
7. 只有 `status="stopped"` 才表示真正关闭完成

相关 warning：
- `stop_recording_retry_succeeded`
- `stop_recording_failed_after_retry`

## 主要工具

### Live tools
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

## 安全默认值

敏感字段默认会被脱敏，包括但不限于：

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

summary 输出应始终视为脱敏视图。

## 已废弃但保留兼容的工具

以下工具仍然存在，但不应继续作为新的主流程入口：

- `proxy_by_time`
- `filter_func`

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

另见：
- [README.en.md](README.en.md)
- [docs/contracts/tools.md](docs/contracts/tools.md)
