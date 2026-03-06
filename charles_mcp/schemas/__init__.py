"""Structured schemas for Charles MCP tools."""

from charles_mcp.schemas.analysis import (
    CaptureAnalysisGroupsResult,
    CaptureAnalysisStatsResult,
    TrafficGroupSummary,
    TrafficDetailResult,
    TrafficQueryResult,
)
from charles_mcp.schemas.history import (
    RecordedTrafficQueryResult,
    RecordingFileInfo,
    RecordingListResult,
    RecordingSnapshotResult,
)
from charles_mcp.schemas.live_capture import (
    LiveCaptureReadResult,
    LiveCaptureStartResult,
    StopLiveCaptureResult,
)
from charles_mcp.schemas.status import (
    ActiveCaptureStatus,
    CharlesStatusConfig,
    CharlesStatusResult,
    LiveCaptureRuntimeStatus,
)

__all__ = [
    "ActiveCaptureStatus",
    "CharlesStatusConfig",
    "CharlesStatusResult",
    "CaptureAnalysisGroupsResult",
    "CaptureAnalysisStatsResult",
    "LiveCaptureReadResult",
    "LiveCaptureStartResult",
    "LiveCaptureRuntimeStatus",
    "RecordedTrafficQueryResult",
    "RecordingFileInfo",
    "RecordingListResult",
    "RecordingSnapshotResult",
    "StopLiveCaptureResult",
    "TrafficGroupSummary",
    "TrafficDetailResult",
    "TrafficQueryResult",
]
