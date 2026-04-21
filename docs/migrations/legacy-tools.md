# Legacy Tool Migration

This page defines migration paths for deprecated compatibility aliases.

## Migration principle

- Prefer canonical tools by source plane:
  - live plane: `start_live_capture` + live analysis/read/detail + `stop_live_capture`
  - history plane: `list_recordings` / `get_recording_snapshot` / `query_recorded_traffic` / `analyze_recorded_traffic`
  - reverse plane: reverse tool surface only

## Legacy mapping table

| Legacy Tool | Status | Direct Replacement | Recommended Migration |
| --- | --- | --- | --- |
| `list_sessions` | deprecated compatibility alias | `list_recordings` | Use `list_recordings` to enumerate snapshots; use `get_recording_snapshot` when full content is required. |
| `filter_func` | deprecated compatibility alias | partial | **Migrate by plane**. For `capture_seconds=0`, use `query_recorded_traffic`. For `capture_seconds>0`, use live workflow: `start_live_capture -> query_live_capture_entries/read_live_capture -> get_traffic_entry_detail (optional) -> stop_live_capture`. |
| `proxy_by_time` | deprecated compatibility alias | no direct replacement | For `record_seconds=0`, use `get_recording_snapshot` or `query_recorded_traffic`. For `record_seconds>0`, use `start_live_capture`, wait externally for N seconds, then `read_live_capture`/`query_live_capture_entries`, then `stop_live_capture(persist=true)`. If historical review is needed, follow with `list_recordings` and `analyze_recorded_traffic`. |

## Removal policy

- Legacy tools are not part of the default public surface.
- Legacy tools are exposed only via explicit compatibility mode.
