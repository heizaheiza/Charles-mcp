"""Source descriptors and probes for official Charles session inputs."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from charles_mcp.reverse.models import CaptureSourceFormat


_SUPPORTED_SUFFIXES: dict[CaptureSourceFormat, tuple[str, ...]] = {
    CaptureSourceFormat.XML: (".xml",),
    CaptureSourceFormat.NATIVE: (".chls", ".chlz"),
    CaptureSourceFormat.LEGACY_JSON: (".chlsj", ".json"),
}


class SessionSource(BaseModel):
    """A filesystem-backed source artifact to ingest into the canonical store."""

    source_format: CaptureSourceFormat
    path: str
    label: str | None = None


class SessionSourceProbe(BaseModel):
    """Validation result for a candidate ingestion source."""

    source_format: CaptureSourceFormat
    path: str
    exists: bool
    size_bytes: int | None = None
    supported: bool
    suffix: str | None = None
    warnings: list[str] = Field(default_factory=list)


def probe_session_source(source: SessionSource) -> SessionSourceProbe:
    """Check basic filesystem and suffix compatibility for a source artifact."""
    path = Path(source.path)
    warnings: list[str] = []
    exists = path.exists()
    suffix = path.suffix.lower() or None
    supported_suffixes = _SUPPORTED_SUFFIXES[source.source_format]
    supported = suffix in supported_suffixes

    if not exists:
        warnings.append("source_not_found")
    if suffix is None:
        warnings.append("missing_suffix")
    elif not supported:
        warnings.append(
            f"unexpected_suffix:{suffix}. expected one of {', '.join(supported_suffixes)}"
        )
    if exists and path.is_dir():
        warnings.append("source_is_directory")
        supported = False
    if source.source_format == CaptureSourceFormat.LEGACY_JSON:
        warnings.append("legacy_data_plane_only_for_compatibility")

    return SessionSourceProbe(
        source_format=source.source_format,
        path=str(path),
        exists=exists,
        size_bytes=path.stat().st_size if exists and path.is_file() else None,
        supported=supported and exists and path.is_file(),
        suffix=suffix,
        warnings=warnings,
    )

