# AGENTS.md

This file defines **global agent behavior rules** for `charles-mcp`.
For task-specific call sequences, see [docs/agent-workflows.md](docs/agent-workflows.md).
For canonical public tool contracts, see [docs/contracts/tools.md](docs/contracts/tools.md).

---

## 1. Global operating model

- **summary first, detail on demand**
- **live and history are separate source planes**
- **reverse analysis extends traffic inspection into replay / decode / signature workflows**
- **state identities must be preserved**: `capture_id`, `cursor`, `recording_path`, `live_session_id`

Do not treat this server as a raw packet dump interface.

---

## 2. Identity and plane rules

1. Never mix source identities:
   - live plane: `capture_id`
   - history plane: `recording_path`
   - reverse imported-analysis plane: reverse `capture_id`
   - reverse live-analysis plane: `live_session_id`
2. Preserve and reuse returned identifiers between calls.
3. Do not infer cross-plane identity fallback in agent logic.

---

## 3. Selection and expansion rules

1. Prefer group/summary tools before detail tools:
   - `group_capture_analysis`
   - `query_live_capture_entries`
   - `analyze_recorded_traffic`
   - `reverse_query_entries`
   - task-oriented reverse live workflow tools
2. Use detail tools only for one confirmed target:
   - `get_traffic_entry_detail`
   - `reverse_get_entry_detail`
3. Do not default to full body expansion:
   - keep `include_full_body=false` unless explicitly needed

---

## 4. Read vs peek semantics

- `read_*` tools consume or advance the current increment/cursor.
- `peek_*` tools preview without consuming or advancing.
- Choose intentionally; do not replace one with the other casually.

---

## 5. Reverse workflow usage principles

1. For reverse imported analysis:
   - narrow with `reverse_query_entries` before detail/decode/replay.
2. For reverse live analysis:
   - preserve `live_session_id`
   - prefer task-oriented tools when goal is known:
     - `reverse_analyze_live_login_flow`
     - `reverse_analyze_live_api_flow`
     - `reverse_analyze_live_signature_flow`
3. For task-oriented outputs:
   - read `summary` and `report` first
   - expand `evidence` only when needed

---

## 6. Recovery and token-budget principles

1. `stop_live_capture`:
   - only `status="stopped"` means fully closed
   - `stop_failed` with `recoverable=true` and `active_capture_preserved=true` means session still exists
2. Prefer status checks over blind retries.
3. Keep token usage low:
   - group first
   - keep `max_items` small
   - avoid bulk detail expansion

