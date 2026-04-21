# Charles MCP Server

[![PyPI version](https://img.shields.io/pypi/v/charles-mcp.svg)](https://pypi.org/project/charles-mcp/)
[![License](https://img.shields.io/pypi/l/charles-mcp.svg)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/charles-mcp.svg)](https://pypi.org/project/charles-mcp/)

[Docs](docs/README.md) | [Tool Contract](docs/contracts/tools.md) | [AGENTS](AGENTS.md) | [Agent Workflow Guide](docs/agent-workflows.md) | [Chinese README](README.md)

Charles MCP Server connects Charles Proxy to MCP clients so an agent can inspect live traffic, analyze saved recordings, and expand individual requests only when needed.

It focuses on three things:

- reading incremental traffic from the current Charles session while recording is still active
- keeping live and history analysis on structured paths instead of exposing raw dump dictionaries first
- using summary-first outputs so the agent can find hotspots before pulling detail

## This Release Direction (v3.0)

The `v3.0` direction is clear: `charles-mcp` is moving from pure traffic inspection toward reverse-engineering workflows.

- On top of existing live/history analysis, it now exposes a reverse-analysis tool surface (import, query, decode, replay, signature candidate discovery, and live reverse sessions).
- The goal is to let an agent go beyond traffic browsing and build an end-to-end reverse workflow around auth flows, signatures, parameter mutation, and replayability.

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

### 2. Install and configure your MCP client

No cloning, no manual virtualenv. Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

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

#### Claude Desktop / Cursor / generic JSON config

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

### Auto-install via AI agent

Copy-paste the following prompt into any AI agent (Claude Code, ChatGPT, Gemini CLI, Cursor Agent, etc.) and it will install and configure charles-mcp automatically:

[![Auto-install Recommended](https://img.shields.io/badge/Auto--install-Recommended-e53935?style=for-the-badge)](#auto-install-via-ai-agent)

<details>
<summary><strong>🔴 Click to expand auto-install prompt (Recommended)</strong></summary>

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
| `CHARLES_REVERSE_STATE_DIR` | `${CHARLES_STATE_DIR}/reverse` | State root for reverse-analysis artifacts and SQLite data |
| `CHARLES_VNEXT_STATE_DIR` | legacy | Legacy reverse-analysis state root. On first startup, `charles-mcp` migrates it into `CHARLES_REVERSE_STATE_DIR` automatically |

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

## Current Version Highlights (v3.0.3)

- The public repository history and provenance wording have been cleaned up: `PROVENANCE.md` was added, and the README now uses a narrower, more verifiable provenance statement.
- Donation-related content has been temporarily removed from the README so the public repository documentation stays focused on the project itself during remediation.
- The default public tool surface is now tightened to canonical 31 tools; legacy aliases (`filter_func`, `proxy_by_time`, `list_sessions`) are no longer exposed by default.
- Added explicit compatibility toggle support: `create_server(expose_legacy_tools=True)` or `CHARLES_EXPOSE_LEGACY_TOOLS=true`.
- Documentation entrypoints now converge on `docs/README.md`, with `docs/migrations/legacy-tools.md` as the authoritative legacy migration guide.
- Added agent execution docs: root-level `AGENTS.md` and task-oriented `docs/agent-workflows.md`.
- Added agent-doc entry links in README and `docs/contracts/tools.md` using repository-relative paths.
- Added minimal guidance semantics to high-frequency entry-tool descriptions (identity preservation, summary-first, peek/read behavior) with contract tests to prevent drift.
- The product direction now explicitly includes reverse engineering: a reverse-analysis tool surface is available for import, decode, replay, signature-candidate discovery, and live reverse workflows.
- `read_live_capture` and `peek_live_capture` now return route-level summary fields only, such as `host`, `method`, `path`, and `status`, instead of raw Charles entries. This keeps repeated polling from blowing up the context window.
- `query_live_capture_entries` is now a read-only analysis path and does not advance the live cursor. You can reuse the same `capture_id` with different filters without consuming the historical increment.
- `analyze_recorded_traffic` and `query_live_capture_entries` summaries now expose `matched_fields` and `match_reasons`, so an agent can explain why a request was selected.
- `get_traffic_entry_detail` now defaults to `include_full_body=false` and `max_body_chars=2048`. When the estimated detail payload exceeds about 12,000 characters, the tool adds a warning suggesting a narrower request.
- Summary and detail output automatically strip `null` values and hide internal fields such as `header_map`, `parsed_json`, `parsed_form`, and `lower_name`. Use the `headers` list when you need header values.

## Tool Catalog

This README documents the recommended tool surface only. Compatibility-only aliases are intentionally not explained here.

### Live capture tools

| Tool | What it does | Typical use |
| --- | --- | --- |
| `start_live_capture` | Starts or adopts the current live capture and returns `capture_id` | Before realtime inspection begins |
| `read_live_capture` | Reads incremental live entries by cursor and returns compact route summaries only | When consuming new traffic continuously and you only need host/path/status first |
| `peek_live_capture` | Previews new live entries without advancing the cursor and returns compact route summaries only | When you want to inspect new traffic without moving the reader state |
| `stop_live_capture` | Stops the capture and optionally persists a snapshot | When closing or exporting a live session |
| `query_live_capture_entries` | Produces structured summary output for a live capture without advancing the cursor | When repeatedly filtering high-value requests out of current traffic |

### Analysis tools

| Tool | What it does | Typical use |
| --- | --- | --- |
| `group_capture_analysis` | Aggregates live or history traffic by group key | When you want the lowest-token hotspot view |
| `get_capture_analysis_stats` | Returns coarse traffic class counts | When you want a quick distribution view |
| `get_traffic_entry_detail` | Loads detail for one specific entry and warns when the payload is too large | After you already identified a target `entry_id` |
| `analyze_recorded_traffic` | Produces structured summary output for a saved recording with match reasons | When analyzing a `.chlsj` snapshot |

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

### Reverse analysis tools

| Tool | What it does | Typical use |
| --- | --- | --- |
| `reverse_import_session` | Imports an official Charles XML or native session into the canonical reverse store | When starting a replay, decode, or signature workflow from saved exports |
| `reverse_list_captures` | Lists imported reverse-analysis captures | When choosing a capture already stored in the reverse SQLite plane |
| `reverse_query_entries` | Filters imported reverse entries by route fields | When narrowing the candidate request set before detail or replay |
| `reverse_get_entry_detail` | Returns canonical detail for one imported reverse entry | When inspecting one baseline request deeply |
| `reverse_decode_entry_body` | Decodes a stored request or response body, including protobuf with descriptors | When you need structured payload understanding |
| `reverse_replay_entry` | Replays one imported request with optional mutations | When validating whether a request can be reproduced or perturbed |
| `reverse_discover_signature_candidates` | Compares multiple imported entries and ranks likely signature-related fields | When searching for dynamic auth or signing parameters |
| `reverse_list_findings` | Lists persisted replay and signature findings | When reviewing prior reverse-analysis evidence |
| `reverse_charles_recording_status` | Reports Charles recording state and reverse live-session state | When checking live reverse-analysis readiness |
| `reverse_start_live_analysis` | Starts a reverse-analysis live session and snapshots Charles via official export pages | When reverse work must track fresh traffic incrementally |
| `reverse_peek_live_entries` | Reads new reverse live entries without advancing the reverse cursor | When previewing new traffic before consuming it |
| `reverse_read_live_entries` | Reads and consumes new reverse live entries | When advancing a reverse live-analysis session |
| `reverse_stop_live_analysis` | Stops a reverse live-analysis session and optionally restores recording | When closing a reverse live session cleanly |
| `reverse_analyze_live_login_flow` | Scores new live traffic for login/auth relevance and summarizes next actions | When tracing login or token bootstrap flows |
| `reverse_analyze_live_api_flow` | Scores new live traffic for API workflow relevance and summarizes next actions | When tracing structured business API traffic |
| `reverse_analyze_live_signature_flow` | Focuses new live traffic on signature-sensitive requests and mutation planning | When targeting signing, nonce, or timestamp defenses |

## Key Behavior

### 1. Raw values are returned by default

This version no longer redacts request or response content:

- summary, detail, live, and history outputs all return raw values
- `include_sensitive` is retained only for compatibility and no longer changes results

### 2. Summary comes before detail

Use `group_capture_analysis`, `query_live_capture_entries`, or `analyze_recorded_traffic` first, then call `get_traffic_entry_detail` only for a confirmed target.

Do not default to `include_full_body=true` unless there is a clear reason.

### 3. Output is optimized for token budgets

All summary and detail outputs have been serialized lean:

- Internal fields like `header_map`, `parsed_json`, `parsed_form`, and `lower_name` are excluded from tool output
- `null` values are stripped automatically during serialization
- When `full_text` is present in a detail view, the redundant `preview_text` is removed

Default parameters have been lowered to protect the context window:

| Parameter | Old default | New default |
| --- | --- | --- |
| `max_items` | 20 | 10 |
| `max_preview_chars` | 256 | 128 |
| `max_headers_per_side` | 8 | 6 |
| `max_body_chars` | 4096 | 2048 |

Higher values can still be passed explicitly when a wider view is needed.

### 4. History detail needs stable source identity

History summaries return `recording_path`. Live summaries return `capture_id`.

For `get_traffic_entry_detail`:

- prefer `recording_path` for history
- prefer `capture_id` for live

### 5. `stop_live_capture` failures are recoverable

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

## Acknowledgments

This project was initially inspired by [tianhetonghua/Charles-mcp-server](https://github.com/tianhetonghua/Charles-mcp-server), and that earlier work deserves explicit credit. The codebase has since been substantially rewritten and reorganized for a different architecture and use case, and is now maintained independently.

The earlier project is oriented more toward reverse engineering and security workflows, with capabilities centered on harvesting, keyword interlocks, encryption detection, and task-scoped cache management. This repository targets a different job: making Charles usable as a stable, low-token, repeatable MCP server for general-purpose AI agents in clients such as Claude Code, Codex, and Cursor.

The later implementation work was driven by concrete gaps I needed to solve:

- a unified model for live capture and history analysis, instead of forcing agents to switch between separate harvesting and filtering mental models
- summary-first, detail-on-demand outputs so agents do not immediately consume large raw dumps and blow up the context window
- stable `capture_id`, `cursor`, and `recording_path` semantics so repeated queries do not accidentally consume or lose live traffic state
- stricter tool contracts, recovery behavior, and protocol consistency for the reliability expectations of the AI agent ecosystem

So this repository has evolved into an independent implementation for a different operating model: more structured, more predictable, and better suited to agents that need to reason over live and historical Charles traffic without fighting the tool surface. A shorter provenance note is available in [PROVENANCE.md](PROVENANCE.md).

## Changelog

### 2026-04-21 (v3.0.3)

- Prepared the repository for a remediated public history release.
- Added `PROVENANCE.md` and narrowed the provenance wording in both README files.
- Temporarily removed donation-related content from the README files so the public documentation remains project-focused during remediation.

### 2026-04-15 (v3.0.2)

- Tightened the default public surface to canonical 31 tools; legacy aliases now live in an explicit compatibility layer and are hidden by default.
- Added compatibility toggles: `expose_legacy_tools` and `CHARLES_EXPOSE_LEGACY_TOOLS` (function argument overrides env).
- Added a docs hub (`docs/README.md`) and legacy migration guide (`docs/migrations/legacy-tools.md`) and unified top-level navigation.
- Updated `docs/contracts/tools.md` to declare canonical public surface semantics and include a stable parseable JSON section for contract tests.

### 2026-04-14 (v3.0.1)

- Added and published agent execution guide docs: root-level `AGENTS.md` and `docs/agent-workflows.md`.
- Added entry links to the agent guides in README and `docs/contracts/tools.md` using repository-relative paths.
- Synced minimal guidance hints for high-frequency entry tools and added documentation/tool-semantic contract tests to keep MCP tool descriptions aligned.

### 2026-04-14 (v3.0.0)

- Introduced the reverse-analysis tool surface for import, query, decode, replay, signature-candidate discovery, and live reverse-analysis workflows. The product scope now goes beyond traffic browsing into reverse-engineering workflows.
- Upgraded live/history structured-analysis behavior: `query_live_capture_entries` remains read-only, summaries expose clearer match reasons, and detail output stays lightweight by default with explicit large-payload warnings.
- Updated documentation to `v3.0` semantics: the new-feature sections in both README files now show explicit version labels.

### 2026-04-13 (v2.0.2)

- Added GitHub Actions release automation for PyPI publishing via Trusted Publisher (OIDC).
- Added release gating with version/tag verification and `twine check --strict`.
- Improved release visibility and metadata so GitHub Release and PyPI publishing stay aligned.

### 2026-03-27 (v2.0.1)

- Restricted history snapshot access to managed `.chlsj` files so the server no longer exposes arbitrary local JSON reads through recording-path inputs.
- Fixed live analysis so `scan_limit` is actually honored instead of silently stopping at a small fixed scan window.
- Fixed `request_body_contains` and `response_body_contains` so matching is no longer limited to clipped preview text.
- Moved installed-runtime snapshots and backups to a user state directory instead of writing runtime data into the package install tree.
- Published `2.0.1` with the fixes above and synced the release across GitHub and PyPI.

## See Also

- [Docs](docs/README.md)
- [Chinese README](README.md)
- [Tool Contract](docs/contracts/tools.md)
