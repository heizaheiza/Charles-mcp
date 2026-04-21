"""Schemas for saved recording history tool contracts."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RecordingFileInfo(BaseModel):
    """Metadata for a saved recording file."""

    filename: str
    size: str
    size_bytes: int
    path: str


class RecordingListResult(BaseModel):
    """Structured result for listing saved recordings."""

    items: list[RecordingFileInfo]
    total_items: int
    warnings: list[str] = Field(default_factory=list)


class RecordedTrafficQueryResult(BaseModel):
    """Structured result for querying saved recording entries."""

    source: Literal["history"]
    path: str | None = None
    items: list[dict[str, Any]]
    total_items: int
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class RecordingSnapshotResult(BaseModel):
    """Structured result for loading a specific saved recording snapshot."""

    source: Literal["history"]
    path: str | None = None
    items: list[dict[str, Any]]
    total_items: int
    warnings: list[str] = Field(default_factory=list)
