"""Ingestion source interfaces for official Charles session formats."""

from .native_convert import NativeSessionConversionError, convert_native_session_to_xml
from .native_session import (
    NativeImportedCaptureGraph,
    NativeImportedEntryGraph,
    parse_charles_native_session,
)
from .sources import SessionSource, SessionSourceProbe, probe_session_source
from .xml_session import ImportedCaptureGraph, ImportedEntryGraph, parse_charles_xml_session

__all__ = [
    "ImportedCaptureGraph",
    "ImportedEntryGraph",
    "NativeSessionConversionError",
    "NativeImportedCaptureGraph",
    "NativeImportedEntryGraph",
    "SessionSource",
    "SessionSourceProbe",
    "convert_native_session_to_xml",
    "parse_charles_native_session",
    "parse_charles_xml_session",
    "probe_session_source",
]
