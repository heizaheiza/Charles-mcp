"""Canonical and compatibility tool surface definitions."""

from __future__ import annotations

CANONICAL_PUBLIC_TOOL_NAMES: tuple[str, ...] = (
    # Live tools
    "start_live_capture",
    "read_live_capture",
    "peek_live_capture",
    "stop_live_capture",
    "query_live_capture_entries",
    # History tools
    "list_recordings",
    "get_recording_snapshot",
    "query_recorded_traffic",
    "analyze_recorded_traffic",
    # Shared analysis tools
    "group_capture_analysis",
    "get_capture_analysis_stats",
    "get_traffic_entry_detail",
    # Status and control tools
    "charles_status",
    "throttling",
    "reset_environment",
    # Reverse tools
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
    "reverse_analyze_live_signature_flow",
)

LEGACY_COMPAT_TOOL_NAMES: tuple[str, ...] = (
    "filter_func",
    "proxy_by_time",
    "list_sessions",
)

