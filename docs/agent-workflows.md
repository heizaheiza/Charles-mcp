# Agent Workflow Guide

This document defines task-oriented calling sequences for agent use.
It complements `AGENTS.md` by focusing on concrete workflows instead of global policy.

---

## 1. Scope

This guide covers four workflow families:

1. live traffic inspection
2. history recording inspection
3. reverse analysis on imported captures
4. reverse analysis on live sessions

Choose the workflow family first.
Do not mix identities across families.

---

## 2. Workflow map

| Goal | Preferred entry | Working identity | End state |
|---|---|---|---|
| Inspect current ongoing traffic | `start_live_capture` | `capture_id` | optional `stop_live_capture` |
| Inspect saved recording | `list_recordings` | `recording_path` | detail on selected entry |
| Decode / replay / compare saved reverse capture | `reverse_import_session` | reverse `capture_id` | findings and experiments |
| Reverse-engineer fresh live flows | `reverse_start_live_analysis` | `live_session_id` | reverse report + evidence |

---

## 3. Workflow A — live traffic hotspot analysis

Use this when the user says things like:

- “看一下我当前抓到的接口”
- “找出正在发生的登录请求”
- “帮我盯着刚刚点按钮产生的新请求”

### A.1 Goal

Find important routes from the active Charles session with minimum token cost, then drill into one confirmed request.

### A.2 Call sequence

#### Step 1 — confirm Charles is reachable

Tool:
- `charles_status`

Read:
- connectivity
- whether an active capture already exists

#### Step 2 — start or adopt a live capture

Tool:
- `start_live_capture`

Recommended defaults:
- `reset_session=true` when starting a fresh investigation
- `adopt_existing=true` only when the user clearly wants to keep current traffic continuity

Save:
- `capture_id`

#### Step 3 — inspect coarse hotspots

Tool:
- `group_capture_analysis`

Recommended arguments:
- `source="live"`
- `capture_id=<capture_id>`
- `group_by="host"` or `group_by="host_path"`
- `preset="api_focus"`

Read first:
- `groups`
- `matched_count`
- `filtered_out_count`
- `warnings`

Decision:
- choose a hot host/path group before touching detail

#### Step 4 — narrow with structured filtering

Tool:
- `query_live_capture_entries`

Recommended filter order:

1. `host_contains`
2. `path_contains`
3. `method_in`
4. `status_in`
5. `request_header_name` / `response_header_name`
6. `request_json_query` / `response_json_query`
7. `request_body_contains` / `response_body_contains`

Read first:
- `items`
- `matched_count`
- `filtered_out_by_class`
- `next_cursor`
- `warnings`

Notes:
- this tool does **not** advance the live cursor
- it is safe to re-query repeatedly with different filters

#### Step 5 — inspect one chosen request

Tool:
- `get_traffic_entry_detail`

Arguments:
- `source="live"`
- `entry_id=<selected entry_id>`
- `capture_id=<capture_id>`
- `include_full_body=false`

Raise detail depth only if needed:
- increase `max_body_chars`
- set `include_full_body=true` only when the raw body is truly necessary

#### Step 6 — stop only when the investigation is done

Tool:
- `stop_live_capture`

Arguments:
- `capture_id=<capture_id>`

Interpretation:
- only `status="stopped"` means closure is complete
- `stop_failed` with `recoverable=true` means you still own a valid session and can continue reading or retry stopping later

### A.3 Fast variant: incremental feed only

If the user only wants newly appeared routes without structured filtering:

- preview: `peek_live_capture`
- consume: `read_live_capture`

Use this variant only when route-level summaries are enough.

### A.4 Anti-patterns

Do not:
- call detail on many entries before grouping
- discard `capture_id`
- assume a failed stop closed the session

---

## 4. Workflow B — history recording analysis

Use this when the user says things like:

- “分析昨天保存的抓包”
- “看某个历史录包里有没有登录接口”
- “从保存的快照里找异常请求”

### B.1 Goal

Analyze saved recordings without touching the active Charles session.

### B.2 Call sequence

#### Step 1 — list available recordings

Tool:
- `list_recordings`

Save:
- chosen `recording_path`

#### Step 2 — inspect structured summary

Tool:
- `analyze_recorded_traffic`

Arguments:
- `recording_path=<recording_path>`
- optional summary filters similar to live analysis

Read first:
- `items`
- `matched_count`
- `filtered_out_count`
- `filtered_out_by_class`
- `warnings`

#### Step 3 — inspect hotspots by dimension

Tool:
- `group_capture_analysis`

Arguments:
- `source="history"`
- `recording_path=<recording_path>`
- `group_by="host" | "path" | "host_path" | "response_status"`

#### Step 4 — drill into one chosen entry

Tool:
- `get_traffic_entry_detail`

Arguments:
- `source="history"`
- `entry_id=<selected entry_id>`
- `recording_path=<recording_path>`

### B.3 Lightweight query shortcut

If the user only needs a quick search on the latest saved recording:

Tool:
- `query_recorded_traffic`

Use for:
- host filter
- method filter
- regex search

Do not substitute it for the main structured analysis path when the user wants richer reasoning.

### B.4 Anti-patterns

Do not:
- use history tools for ongoing live traffic
- omit `recording_path` when drilling into history detail
- silently switch to latest recording after the user already chose one

---

## 5. Workflow C — reverse analysis on imported captures

Use this when the user says things like:

- “把这个 Charles 导出的 xml 导进来分析”
- “找一下哪些参数像 sign / nonce / timestamp”
- “回放这个请求试试看能不能复现”
- “帮我把 protobuf body 解一下”

### C.1 Goal

Turn a saved Charles export into a canonical reverse-analysis dataset, then perform narrowing, decode, signature discovery, replay, and evidence review.

### C.2 Call sequence

#### Step 1 — import the exported session

Tool:
- `reverse_import_session`

Arguments:
- `path=<path to Charles export>`
- `source_format="xml"` or `"native"`
- `source_kind="history_import"` unless there is a specific alternative workflow reason

Save:
- reverse `capture_id`

#### Step 2 — narrow candidate requests

Tool:
- `reverse_query_entries`

Arguments:
- `capture_id=<reverse capture_id>`
- optional route filters:
  - `host_contains`
  - `path_contains`
  - `method_in`
  - `status_in`

Read first:
- returned item list
- count and offset coverage

Use this step to find comparable requests before any decode or replay.

#### Step 3 — inspect the baseline request deeply

Tool:
- `reverse_get_entry_detail`

Arguments:
- `entry_id=<selected entry_id>`

Read first:
- request metadata
- response metadata
- body availability
- any canonicalized fields that help with replay planning

#### Step 4 — decode request or response body when structure matters

Tool:
- `reverse_decode_entry_body`

Arguments:
- `entry_id=<selected entry_id>`
- `side="request"` or `"response"`
- optional `descriptor_path`
- optional `message_type`

Use this when:
- content is protobuf
- binary payload structure matters
- raw text is not enough to reason about fields

#### Step 5 — compare similar entries for signing hints

Tool:
- `reverse_discover_signature_candidates`

Arguments:
- `entry_ids=[...]`

Recommended practice:
- provide 2–3 similar requests from the same route family
- compare requests that differ in payload, timestamp, cookie, or auth state

Read first:
- ranked `candidates`
- likely signature-related fields

#### Step 6 — run a focused replay or mutation test

Tool:
- `reverse_replay_entry`

Arguments:
- `entry_id=<selected entry_id>`
- optional overrides:
  - `query_overrides`
  - `header_overrides`
  - `json_overrides`
  - `form_overrides`
  - `body_text_override`
  - `follow_redirects`
  - `use_proxy`

Use replay only after you have selected a stable baseline request.

#### Step 7 — review persisted findings

Tool:
- `reverse_list_findings`

Use this to recover earlier evidence after replay or signature analysis.

### C.3 Suggested operating patterns

#### Pattern 1 — replayability check

1. `reverse_import_session`
2. `reverse_query_entries`
3. `reverse_get_entry_detail`
4. `reverse_replay_entry`
5. `reverse_list_findings`

#### Pattern 2 — signature hunting

1. `reverse_import_session`
2. `reverse_query_entries`
3. choose 2–3 similar entries
4. `reverse_discover_signature_candidates`
5. `reverse_replay_entry` with one focused mutation

#### Pattern 3 — protobuf understanding

1. `reverse_import_session`
2. `reverse_query_entries`
3. `reverse_get_entry_detail`
4. `reverse_decode_entry_body`

### C.4 Anti-patterns

Do not:
- replay arbitrary entries before narrowing candidates
- compare unrelated endpoints for signature detection
- ask for decode before confirming the entry actually matters

---

## 6. Workflow D — reverse live session analysis

Use this when the user says things like:

- “我现在准备登录，帮我盯住登录链路”
- “我现在操作 app，你帮我找签名字段”
- “边抓边分析刚产生的新接口”

### D.1 Goal

Analyze fresh Charles traffic incrementally through the reverse-analysis plane, using either generic read tools or task-oriented workflow tools.

### D.2 Session setup

#### Step 1 — inspect current reverse readiness

Tool:
- `reverse_charles_recording_status`

Read:
- Charles recording state
- any existing reverse live-session state

#### Step 2 — start the reverse live-analysis session

Tool:
- `reverse_start_live_analysis`

Recommended defaults:
- `reset_session=false`
- `start_recording_if_stopped=true`
- `snapshot_format="xml"`

Save:
- `live_session_id`

#### Step 3 — user performs the action of interest

Examples:
- login
- refresh token
- submit signed API request
- navigate to a screen that triggers the protected API

### D.3 Generic reverse live read path

Use this when the goal is still broad or exploratory.

#### Preview without consuming

Tool:
- `reverse_peek_live_entries`

Arguments:
- `live_session_id=<live_session_id>`
- optional route filters
- `snapshot_format="xml"`

Use when:
- you want to see whether relevant traffic already appeared
- you are not ready to advance the cursor

#### Consume the new increment

Tool:
- `reverse_read_live_entries`

Use when:
- you are ready to move the live cursor forward
- you want only new entries after the last read

### D.4 Task-oriented reverse live path

Use one of the following when the investigation goal is already known.

#### D.4.1 Login / auth tracing

Tool:
- `reverse_analyze_live_login_flow`

Best for:
- login handshakes
- token issuance
- cookie establishment
- auth redirect chains

Recommended inputs:
- `live_session_id`
- optional `host_contains`
- optional `path_keywords`
- `decode_bodies=true`
- `run_replay=false` on first pass

#### D.4.2 Business API tracing

Tool:
- `reverse_analyze_live_api_flow`

Best for:
- tracing structured app/API workflows
- finding the highest-value request from a burst of traffic
- selecting replay candidates with report output

#### D.4.3 Signature / dynamic parameter tracing

Tool:
- `reverse_analyze_live_signature_flow`

Best for:
- sign / nonce / timestamp defenses
- field ranking for mutation planning
- focusing on requests likely guarded by dynamic verification

Useful extra input:
- `signature_hints`

### D.5 How to read task-oriented outputs

These reverse live workflow tools return more than a candidate list.
Treat them as three layers:

#### Layer 1 — `summary`

Read first when you want the fast answer.

Important fields:
- `selected_entry_id`
- `candidate_count`
- `signature_candidate_fields`
- `replay_outcome`
- `mutation_plan_overview`

#### Layer 2 — `report`

Read this for concise reasoning and next-step planning.

Important fields:
- `overview`
- `candidate_assessment`
- `selected_request`
- `decoded_observations`
- `signature_analysis`
- `replay_analysis`
- `mutation_strategy`
- `recommended_next_actions`

#### Layer 3 — `evidence`

Read this only when you need supporting artifacts.

Important fields:
- `live_read`
- `selected_entry_detail`
- `decoded_request`
- `decoded_response`
- `signature_candidates`
- `replay_result`
- `related_findings`
- `mutation_plan`

### D.6 Recommended use patterns

#### Pattern 1 — login discovery

1. `reverse_start_live_analysis`
2. user performs login
3. `reverse_analyze_live_login_flow`
4. read `summary.selected_entry_id`
5. read `report.recommended_next_actions`
6. optionally stop session

#### Pattern 2 — signature hunting on fresh traffic

1. `reverse_start_live_analysis`
2. user triggers a protected request multiple times
3. `reverse_analyze_live_signature_flow`
4. read `summary.signature_candidate_fields`
5. read `evidence.signature_candidates`
6. decide whether to replay or mutate later

#### Pattern 3 — exploratory fresh traffic pass

1. `reverse_start_live_analysis`
2. `reverse_peek_live_entries`
3. if relevant traffic appears, call `reverse_read_live_entries`
4. switch to a task-oriented workflow tool once the goal is clear

### D.7 Closing the session

Tool:
- `reverse_stop_live_analysis`

Arguments:
- `live_session_id=<live_session_id>`
- `restore_recording=true`

Use this when the reverse live investigation is finished.

### D.8 Anti-patterns

Do not:
- discard `live_session_id`
- use `read` when you only meant to preview
- jump straight to generic replay before reading the workflow report
- treat the `evidence` block as the first thing to read on every call

---

## 7. Workflow selection cheatsheet

### User wants “现在正在发生的请求”

Use:
- Workflow A

### User wants “保存好的抓包”

Use:
- Workflow B

### User has exported XML/native session and wants reverse engineering

Use:
- Workflow C

### User wants to watch fresh app traffic and reason about auth/signature flows in real time

Use:
- Workflow D

---

## 8. Response policy for agents

When reporting findings back to the user:

1. start from the selected route or request
2. explain why it was selected
3. mention whether body decoding succeeded
4. mention whether signature-like fields were found
5. mention whether replay preserved or changed behavior
6. recommend the next focused experiment instead of dumping all raw evidence immediately

---

## 9. Minimal examples

### Example 1 — live hotspot review

```text
charles_status
start_live_capture
group_capture_analysis(source="live", group_by="host_path", capture_id=...)
query_live_capture_entries(capture_id=..., host_contains="api.example.com", path_contains="login")
get_traffic_entry_detail(source="live", capture_id=..., entry_id=...)
stop_live_capture(capture_id=...)
```

### Example 2 — imported reverse signature search

```text
reverse_import_session(path="/path/to/export.xml")
reverse_query_entries(capture_id=..., host_contains="api.example.com", path_contains="/v1/order")
reverse_discover_signature_candidates(entry_ids=["...", "...", "..."])
reverse_replay_entry(entry_id="...", json_overrides={"timestamp": 0})
reverse_list_findings(subject_id="...")
```

### Example 3 — live login reverse workflow

```text
reverse_charles_recording_status
reverse_start_live_analysis(snapshot_format="xml")
# user performs login
reverse_analyze_live_login_flow(live_session_id=..., host_contains="api.example.com", path_keywords=["login", "token", "auth"])
reverse_stop_live_analysis(live_session_id=...)
```

---

## 10. Final rule

Choose the workflow that matches the user’s real task, preserve the returned identity, and always prefer:

- summary before detail
- selection before replay
- structured report before raw evidence
