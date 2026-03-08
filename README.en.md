# Charles MCP Server

[Chinese README](README.md) | [Tool Contract](docs/contracts/tools.md)

Charles MCP Server connects Charles Proxy to MCP clients so an agent can inspect live traffic, analyze saved recordings, and expand individual requests only when needed.

It focuses on three things:

- reading incremental traffic from the current Charles session while recording is still active
- keeping live and history analysis on structured paths instead of exposing raw dump dictionaries first
- using summary-first outputs so the agent can find hotspots before pulling detail

## Quick Start

### 1. Enable the Charles Web Interface

In Charles, open: `Proxy -> Web Interface Settings`

Make sure:

- `Enable web interface` is checked
- username is `admin`
- password is `123456`

Menu location:

![Charles Web Interface Menu](docs/images/charles-web-interface-menu.png)

Settings dialog:

![Charles Web Interface Settings](docs/images/charles-web-interface-settings.png)

### 2. Install

```bash
pip install -e .[dev]
```

Installed command:

```bash
charles-mcp
```

Package entrypoint:

```text
charles_mcp.main:main
```

Repository-local compatibility entrypoint:

```bash
python charles-mcp-server.py
```

### 3. Set environment variables and start the server

#### PowerShell

```powershell
$env:CHARLES_USER = "admin"
$env:CHARLES_PASS = "123456"
$env:CHARLES_PROXY_HOST = "127.0.0.1"
$env:CHARLES_PROXY_PORT = "8888"
$env:CHARLES_MANAGE_LIFECYCLE = "false"
charles-mcp
```

#### Windows CMD

```cmd
set CHARLES_USER=admin
set CHARLES_PASS=123456
set CHARLES_PROXY_HOST=127.0.0.1
set CHARLES_PROXY_PORT=8888
set CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

#### Git Bash / Bash / Zsh

```bash
export CHARLES_USER=admin
export CHARLES_PASS=123456
export CHARLES_PROXY_HOST=127.0.0.1
export CHARLES_PROXY_PORT=8888
export CHARLES_MANAGE_LIFECYCLE=false
charles-mcp
```

#### Direct Python entrypoint

```bash
python -c "from charles_mcp.main import main; main()"
```

### 4. Register it in your MCP client

Generic stdio MCP configuration:

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

#### Claude CLI

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

#### Codex CLI

```toml
[mcp_servers.charles]
command = "charles-mcp"

[mcp_servers.charles.env]
CHARLES_USER = "admin"
CHARLES_PASS = "123456"
CHARLES_MANAGE_LIFECYCLE = "false"
```

#### Antigravity

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

## Requirements

- Python 3.10+
- Charles Proxy running locally
- Charles Web Interface enabled
- Charles proxy listening on `127.0.0.1:8888`

`CHARLES_MANAGE_LIFECYCLE=false` is the recommended default. Unless you explicitly want the MCP server to manage Charles lifecycle, do not let it shut down your own Charles process.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `CHARLES_USER` | `admin` | Charles Web Interface username |
| `CHARLES_PASS` | `123456` | Charles Web Interface password |
| `CHARLES_PROXY_HOST` | `127.0.0.1` | Charles proxy host |
| `CHARLES_PROXY_PORT` | `8888` | Charles proxy port |
| `CHARLES_CONFIG_PATH` | auto-detect | Charles config file path |
| `CHARLES_REQUEST_TIMEOUT` | `10` | Control-plane HTTP timeout in seconds |
| `CHARLES_MAX_STOPTIME` | `3600` | Maximum bounded recording length |
| `CHARLES_MANAGE_LIFECYCLE` | `false` | Whether the MCP server should manage Charles startup and shutdown |

## Recommended Flows

### Live analysis

1. `start_live_capture`
2. `group_capture_analysis`
3. `query_live_capture_entries`
4. `get_traffic_entry_detail`
5. `stop_live_capture`

This path is optimized for finding hotspots first, then drilling down into one confirmed request.

### History analysis

1. `list_recordings`
2. `analyze_recorded_traffic`
3. `group_capture_analysis(source="history")`
4. `get_traffic_entry_detail`

This path is optimized for browsing saved recordings and then drilling into selected entries.

## Tool Catalog

This README documents the recommended tool surface only. Compatibility-only aliases are intentionally not explained here.

### Live capture tools

| Tool | What it does | Typical use |
| --- | --- | --- |
| `start_live_capture` | Starts or adopts the current live capture and returns `capture_id` | Before realtime inspection begins |
| `read_live_capture` | Reads incremental live entries by cursor | When consuming new traffic continuously |
| `peek_live_capture` | Previews new live entries without advancing the cursor | When you want to inspect new traffic without moving the reader state |
| `stop_live_capture` | Stops the capture and optionally persists a snapshot | When closing or exporting a live session |
| `query_live_capture_entries` | Produces structured summary output for a live capture | When filtering high-value requests out of current traffic |

### Analysis tools

| Tool | What it does | Typical use |
| --- | --- | --- |
| `group_capture_analysis` | Aggregates live or history traffic by group key | When you want the lowest-token hotspot view |
| `get_capture_analysis_stats` | Returns coarse traffic class counts | When you want a quick distribution view |
| `get_traffic_entry_detail` | Loads detail for one specific entry | After you already identified a target `entry_id` |
| `analyze_recorded_traffic` | Produces structured summary output for a saved recording | When analyzing a `.chlsj` snapshot |

### History tools

| Tool | What it does | Typical use |
| --- | --- | --- |
| `list_recordings` | Lists saved recording files | Before choosing a historical snapshot |
| `get_recording_snapshot` | Loads the raw content of one saved recording | When you need the stored snapshot itself |
| `query_recorded_traffic` | Applies lightweight filtering to the latest saved recording | When you need a quick host, method, or regex query |

### Status and control tools

| Tool | What it does | Typical use |
| --- | --- | --- |
| `charles_status` | Reports Charles connectivity and active capture state | When checking whether Charles is reachable or capture is still active |
| `throttling` | Applies a Charles network throttling preset | When simulating 3G, 4G, 5G, or disabling throttling |
| `reset_environment` | Restores Charles configuration and clears the current environment | When you need to return to a clean baseline |

## Key Behavior

### 1. Raw values are returned by default

This version no longer redacts request or response content:

- summary, detail, live, and history outputs all return raw values
- `include_sensitive` is retained only for compatibility and no longer changes results

### 2. Summary comes before detail

Use `group_capture_analysis`, `query_live_capture_entries`, or `analyze_recorded_traffic` first, then call `get_traffic_entry_detail` only for a confirmed target.

Do not default to `include_full_body=true` unless there is a clear reason.

### 3. History detail needs stable source identity

History summaries return `recording_path`. Live summaries return `capture_id`.

For `get_traffic_entry_detail`:

- prefer `recording_path` for history
- prefer `capture_id` for live

### 4. `stop_live_capture` failures are recoverable

`stop_live_capture` has two stable end states:

- `status="stopped"` means the capture is actually closed
- `status="stop_failed"` means a short retry also failed but the capture is still preserved

When the result is:

```json
{
  "status": "stop_failed",
  "recoverable": true,
  "active_capture_preserved": true
}
```

the capture is still readable and can be diagnosed or stopped again later.

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

## Support

If this project helps your work, you can support future maintenance and iteration.

### WeChat donation QR

![WeChat donation QR](docs/images/wechat-donate.png)

### USDT-TRC20

`TCudxn9ByCxPZHXLtvqBjFmLWXywBoicRs`

## See Also

- [Chinese README](README.md)
- [Tool Contract](docs/contracts/tools.md)
