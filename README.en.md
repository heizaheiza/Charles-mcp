# Charles MCP Server

[Chinese README](README.md) | [Tool Contract](docs/contracts/tools.md)

Charles MCP Server integrates Charles Proxy with MCP clients and is designed for agent-driven traffic inspection.

Core capabilities:

- Read incremental data from the current Charles session while recording is active
- Keep live and history traffic analysis on separate paths
- Prefer high-value API requests and filter out noisy assets such as images, fonts, media, and tunnels
- Apply redaction by default so tokens, cookies, and authorization headers are not exposed by default
- Use summary-first outputs to reduce agent token usage and only expand details on demand

## Highlights

1. Realtime capture that agents can actually read
- `start_live_capture`
- `read_live_capture`
- `peek_live_capture`
- `stop_live_capture`

2. Token-aware traffic analysis
- `query_live_capture_entries`
- `analyze_recorded_traffic`
- `group_capture_analysis`
- Default `preset="api_focus"`
- Default filtering of `static_asset`, `media`, `font`, `connect_tunnel`, and other low-value traffic

3. Structured drill-down
- `get_traffic_entry_detail`
- Redacted detail by default
- Full request or response bodies only when explicitly requested

4. Safer stop semantics
- `stop_live_capture` performs one short retry internally
- If both stop attempts fail, the tool returns `status="stop_failed"`
- It also returns `recoverable=true` and `active_capture_preserved=true`
- This means the active capture is still preserved and the agent can continue reading or retry stopping it

## Requirements

- Python 3.10+
- Charles Proxy running locally
- Charles Web Interface enabled
- Charles proxy listening on `127.0.0.1:8888` unless overridden

## Install

```bash
pip install -e .[dev]
```

Installed command:

```bash
charles-mcp
```

Package entrypoint target:

```text
charles_mcp.main:main
```

Repository-local compatibility entrypoint:

```bash
python charles-mcp-server.py
```

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `CHARLES_USER` | `admin` | Charles Web Interface username |
| `CHARLES_PASS` | `123456` | Charles Web Interface password |
| `CHARLES_PROXY_HOST` | `127.0.0.1` | Charles proxy host |
| `CHARLES_PROXY_PORT` | `8888` | Charles proxy port |
| `CHARLES_CONFIG_PATH` | auto-detect | Charles config file path |
| `CHARLES_REQUEST_TIMEOUT` | `10` | Control plane HTTP timeout in seconds |
| `CHARLES_MAX_STOPTIME` | `3600` | Maximum bounded recording length |
| `CHARLES_MANAGE_LIFECYCLE` | `false` | Whether the MCP server should manage Charles startup/shutdown lifecycle |

`CHARLES_MANAGE_LIFECYCLE=false` is the recommended default. The MCP server should not shut down the user's Charles process unless lifecycle management is explicitly enabled.

## Terminal setup examples

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

### Direct Python entrypoint

```bash
python -c "from charles_mcp.main import main; main()"
```

## MCP client configuration examples

### Generic stdio MCP configuration

Use this when your MCP client supports `command + args + env`.

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

The official Claude Code / Claude CLI flow supports adding stdio MCP servers with `claude mcp add-json`:

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

For repository-local development, point Claude CLI at the project entrypoint directly:

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

Verify the server entry:

```bash
claude mcp get charles
```

### Codex CLI

Codex CLI reads MCP servers from `~/.codex/config.toml`. Recommended configuration:

```toml
[mcp_servers.charles]
command = "charles-mcp"

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

Repository-local development variant:

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

Antigravity supports editing raw `mcpServers` JSON through its MCP management UI. Add a config like this in `Manage MCP Servers` or `View raw config`:

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

Repository-local development variant:

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

### Direct Python entrypoint

```bash
python -c "from charles_mcp.main import main; main()"
```
## Recommended usage flows

### Live analysis flow

Recommended order for agents:

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

Why this order works:
- `group_capture_analysis` is the lowest-token way to find hotspots first
- `query_live_capture_entries` returns structured summaries
- `get_traffic_entry_detail` is only for targeted drill-down

### History analysis flow

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

## Agent contract for `stop_failed + recoverable=true`

`stop_live_capture` has two stable end states:

1. `status="stopped"`
- Stop succeeded
- The active capture was closed
- `persisted_path` may be present when `persist=true`

2. `status="stop_failed"`
- Stop still failed after one short retry
- This does not mean the live capture is closed
- Interpret it together with:
  - `recoverable=true`
  - `active_capture_preserved=true`

When the tool returns:

```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

the agent should:

1. Keep the `capture_id`
2. Not assume Charles has stopped recording
3. Inspect `error` and `warnings`
4. Call `charles_status` if current capture state needs confirmation
5. Call `read_live_capture` if traffic still needs to be inspected
6. Retry `stop_live_capture` when cleanup should continue
7. Only treat the capture as closed when `status="stopped"`

Related warning values:
- `stop_recording_retry_succeeded`
- `stop_recording_failed_after_retry`

## Main tools

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

### Status and control tools
- `charles_status`
- `throttling`
- `reset_environment`

## Security defaults

Sensitive values are redacted by default. This includes, but is not limited to:

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

Summary output should always be treated as a redacted view.

## Deprecated tools

These tools still exist for compatibility, but they should not be extended for the main agent workflow:

- `proxy_by_time`
- `filter_func`

## Development

Run tests:

```bash
python -m pytest -q
```

Useful local checks:

```bash
python charles-mcp-server.py
python -c "from charles_mcp.main import main; main()"
```

See also:
- [Chinese README](README.md)
- [Tool Contract](docs/contracts/tools.md)
