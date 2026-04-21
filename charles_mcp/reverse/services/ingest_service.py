"""Import official Charles session formats into the canonical store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from charles_mcp.reverse.config import VNextConfig
from charles_mcp.reverse.ingest import (
    SessionSource,
    convert_native_session_to_xml,
    parse_charles_native_session,
    parse_charles_xml_session,
    probe_session_source,
)
from charles_mcp.reverse.models import CaptureSourceFormat, CaptureSourceKind
from charles_mcp.reverse.services.common import new_identifier
from charles_mcp.reverse.storage import SQLiteStore


class IngestService:
    """Import XML/native Charles sessions and persist them in SQLite."""

    def __init__(self, config: VNextConfig, store: SQLiteStore) -> None:
        self.config = config
        self.store = store

    def import_session(
        self,
        *,
        path: str,
        source_format: CaptureSourceFormat,
        source_kind: CaptureSourceKind = CaptureSourceKind.HISTORY_IMPORT,
    ) -> dict:
        source = SessionSource(source_format=source_format, path=path)
        probe = probe_session_source(source)
        if not probe.supported:
            raise ValueError(
                f"unsupported session source: {probe.path}. warnings={probe.warnings}"
            )

        capture_id = new_identifier("capture")
        xml_path = Path(path)
        warnings = list(probe.warnings)
        metadata: dict[str, object] = {"input_path": path}
        imported: Any

        if source_format == CaptureSourceFormat.NATIVE:
            try:
                imported = parse_charles_native_session(
                    path,
                    capture_id=capture_id,
                    source_kind=source_kind,
                )
            except Exception:
                if not self.config.charles_cli_path:
                    raise ValueError(
                        "native session parsing failed and CHARLES_CLI_PATH is unavailable for conversion fallback"
                    ) from None
                target_path = self.config.temp_dir / f"{capture_id}.xml"
                xml_path = convert_native_session_to_xml(
                    charles_cli_path=self.config.charles_cli_path,
                    source_path=path,
                    target_path=target_path,
                )
                warnings.append("native_session_converted_to_xml")
                metadata["converted_xml_path"] = str(xml_path)
                imported = parse_charles_xml_session(
                    xml_path,
                    capture_id=capture_id,
                    source_kind=source_kind,
                )
            imported.capture.metadata.update(metadata)
            return self._persist_imported(imported, warnings=warnings)

        if source_format == CaptureSourceFormat.LEGACY_JSON:
            raise ValueError("legacy JSON import is not implemented in vnext")

        imported = parse_charles_xml_session(
            xml_path,
            capture_id=capture_id,
            source_kind=source_kind,
        )
        imported.capture.metadata.update(metadata)
        return self._persist_imported(imported, warnings=warnings)

    def _persist_imported(self, imported: Any, *, warnings: list[str]) -> dict[str, Any]:
        """Persist a parsed capture graph in one transaction."""
        with self.store.transaction():
            self.store.upsert_capture(imported.capture)
            for graph in imported.entries:
                for body_blob in graph.body_blobs:
                    self.store.upsert_body_blob(body_blob)
                self.store.upsert_entry(graph.entry, graph.request, graph.response)

        return {
            "capture_id": imported.capture.capture_id,
            "source_format": imported.capture.source_format.value,
            "source_kind": imported.capture.source_kind.value,
            "entry_count": imported.capture.entry_count,
            "warnings": warnings + imported.warnings,
            "metadata": imported.capture.metadata,
        }

