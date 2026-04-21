"""Reverse-analysis runtime and tool registration for Charles MCP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from charles_mcp.config import Config, get_config as get_base_config
from charles_mcp.reverse.config import VNextConfig, build_reverse_config
from charles_mcp.reverse.models import CaptureSourceFormat, CaptureSourceKind
from charles_mcp.reverse.services import (
    DecodeService,
    IngestService,
    LiveAnalysisService,
    QueryService,
    ReplayService,
    WorkflowService,
)
from charles_mcp.reverse.services.charles_control_service import (
    CharlesControlConfig,
    CharlesControlService,
)
from charles_mcp.reverse.storage import SQLiteStore


LiveSnapshotFormatParam = Annotated[
    str,
    Field(
        description="Supported live snapshot export formats: `xml` or `native`.",
        json_schema_extra={"enum": ["xml", "native"]},
    ),
]


@dataclass(frozen=True)
class LiveSnapshotFormatResolution:
    snapshot_format: CaptureSourceFormat
    input_warnings: tuple[str, ...] = ()
    coerced_from: str | None = None


@dataclass(frozen=True)
class ReverseRuntime:
    config: VNextConfig
    store: SQLiteStore
    ingest_service: IngestService
    query_service: QueryService
    decode_service: DecodeService
    replay_service: ReplayService
    control_service: CharlesControlService
    live_service: LiveAnalysisService
    workflow_service: WorkflowService


def _coerce_live_snapshot_format(snapshot_format: str | CaptureSourceFormat) -> LiveSnapshotFormatResolution:
    """Normalize live snapshot format input and reject unsupported values clearly."""
    if isinstance(snapshot_format, CaptureSourceFormat):
        normalized = snapshot_format.value
    else:
        normalized = str(snapshot_format).strip().lower()

    if normalized == "summary":
        return LiveSnapshotFormatResolution(
            snapshot_format=CaptureSourceFormat.XML,
            input_warnings=(
                "`snapshot_format=summary` is deprecated for live-session tools; using `xml`.",
            ),
            coerced_from="summary",
        )

    if normalized not in {CaptureSourceFormat.XML.value, CaptureSourceFormat.NATIVE.value}:
        raise ValueError("`snapshot_format` for live-session tools must be `xml` or `native`.")

    return LiveSnapshotFormatResolution(snapshot_format=CaptureSourceFormat(normalized))


def _with_live_snapshot_resolution(
    result: dict[str, Any],
    resolution: LiveSnapshotFormatResolution,
) -> dict[str, Any]:
    """Attach any live snapshot input coercion metadata to the tool result."""
    if not resolution.input_warnings and resolution.coerced_from is None:
        return result

    enriched = dict(result)
    if resolution.input_warnings:
        enriched["input_warnings"] = list(resolution.input_warnings)
    if resolution.coerced_from is not None:
        enriched["coerced_from"] = {"snapshot_format": resolution.coerced_from}
    return enriched


def build_reverse_runtime(config: Config | None = None) -> ReverseRuntime:
    """Build the reverse-analysis runtime from the main Charles MCP config."""
    base_config = config or get_base_config()
    reverse_config = build_reverse_config(base_config)
    store = SQLiteStore(reverse_config.database_path)
    ingest_service = IngestService(reverse_config, store)
    query_service = QueryService(store)
    decode_service = DecodeService(store)
    replay_service = ReplayService(reverse_config, store)
    control_service = CharlesControlService(
        CharlesControlConfig(
            user=reverse_config.charles_user,
            password=reverse_config.charles_pass,
            base_url=reverse_config.charles_base_url,
            proxy_url=reverse_config.charles_proxy_url,
            timeout_seconds=reverse_config.replay_timeout_seconds,
        )
    )
    live_service = LiveAnalysisService(
        control_service=control_service,
        ingest_service=ingest_service,
        query_service=query_service,
        temp_dir=reverse_config.temp_dir,
        session_ttl_seconds=reverse_config.live_session_ttl_seconds,
        snapshot_history_limit=reverse_config.live_session_snapshot_history_limit,
    )
    workflow_service = WorkflowService(
        live_service=live_service,
        query_service=query_service,
        decode_service=decode_service,
        replay_service=replay_service,
    )
    return ReverseRuntime(
        config=reverse_config,
        store=store,
        ingest_service=ingest_service,
        query_service=query_service,
        decode_service=decode_service,
        replay_service=replay_service,
        control_service=control_service,
        live_service=live_service,
        workflow_service=workflow_service,
    )


def register_reverse_tools(mcp: FastMCP, runtime: ReverseRuntime) -> None:
    """Register reverse-analysis tools on an existing FastMCP server."""
    config = runtime.config
    ingest_service = runtime.ingest_service
    query_service = runtime.query_service
    decode_service = runtime.decode_service
    replay_service = runtime.replay_service
    live_service = runtime.live_service
    workflow_service = runtime.workflow_service

    @mcp.tool()
    def reverse_import_session(
        path: str,
        source_format: str = "xml",
        source_kind: str = "history_import",
    ) -> dict[str, Any]:
        """Import an official Charles XML/native session into the canonical reverse-analysis store."""
        return ingest_service.import_session(
            path=path,
            source_format=CaptureSourceFormat(source_format),
            source_kind=CaptureSourceKind(source_kind),
        )

    @mcp.tool()
    def reverse_list_captures(limit: int = 20) -> list[dict[str, Any]]:
        """List imported captures from the local SQLite store."""
        return query_service.list_captures(limit=min(limit, config.max_query_limit))

    @mcp.tool()
    def reverse_query_entries(
        capture_id: str,
        host_contains: str | None = None,
        path_contains: str | None = None,
        method_in: list[str] | None = None,
        status_in: list[int] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query imported entries using route-level filters.
        Use this as the summary-first narrowing step for a reverse capture_id."""
        return query_service.query_entries(
            capture_id=capture_id,
            host_contains=host_contains,
            path_contains=path_contains,
            method_in=method_in,
            status_in=status_in,
            limit=min(limit, config.max_query_limit),
            offset=max(offset, 0),
        )

    @mcp.tool()
    def reverse_get_entry_detail(entry_id: str) -> dict[str, Any]:
        """Get the canonical detail view for one imported entry.
        Use after candidate selection; this is not a bulk-browsing endpoint."""
        return query_service.get_entry_detail(entry_id=entry_id)

    @mcp.tool()
    def reverse_decode_entry_body(
        entry_id: str,
        side: str,
        descriptor_path: str | None = None,
        message_type: str | None = None,
    ) -> dict[str, Any]:
        """Decode a stored request/response body, including protobuf when a descriptor is provided."""
        return decode_service.decode_entry_body(
            entry_id=entry_id,
            side=side,
            descriptor_path=descriptor_path,
            message_type=message_type,
        )

    @mcp.tool()
    async def reverse_replay_entry(
        entry_id: str,
        query_overrides: dict[str, Any] | None = None,
        header_overrides: dict[str, str | None] | None = None,
        json_overrides: dict[str, Any] | None = None,
        form_overrides: dict[str, Any] | None = None,
        body_text_override: str | None = None,
        follow_redirects: bool = True,
        use_proxy: bool = False,
    ) -> dict[str, Any]:
        """Replay one imported entry with optional mutations and store the experiment result."""
        return await replay_service.replay_entry(
            entry_id=entry_id,
            query_overrides=query_overrides,
            header_overrides=header_overrides,
            json_overrides=json_overrides,
            form_overrides=form_overrides,
            body_text_override=body_text_override,
            follow_redirects=follow_redirects,
            use_proxy=use_proxy,
        )

    @mcp.tool()
    def reverse_discover_signature_candidates(entry_ids: list[str]) -> dict[str, Any]:
        """Compare multiple requests and rank fields that look signature-related."""
        return query_service.discover_signature_candidates(entry_ids=entry_ids)

    @mcp.tool()
    def reverse_list_findings(
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List persisted findings from replay or signature-candidate analysis."""
        return query_service.list_findings(subject_type=subject_type, subject_id=subject_id)

    @mcp.tool()
    async def reverse_charles_recording_status(
        live_session_id: str | None = None,
    ) -> dict[str, Any]:
        """Inspect Charles recording state and optional reverse live-session state."""
        return await live_service.status(live_session_id=live_session_id)

    @mcp.tool()
    async def reverse_start_live_analysis(
        reset_session: bool = False,
        start_recording_if_stopped: bool = True,
        snapshot_format: LiveSnapshotFormatParam = "xml",
    ) -> dict[str, Any]:
        """Start a near-real-time live analysis session without using undocumented JSON export.
        Preserve and reuse live_session_id for follow-up reverse live tools."""
        resolution = _coerce_live_snapshot_format(snapshot_format)
        result = await live_service.start(
            reset_session=reset_session,
            start_recording_if_stopped=start_recording_if_stopped,
            snapshot_format=resolution.snapshot_format,
        )
        return _with_live_snapshot_resolution(result, resolution)

    @mcp.tool()
    async def reverse_peek_live_entries(
        live_session_id: str,
        snapshot_format: LiveSnapshotFormatParam = "xml",
        host_contains: str | None = None,
        path_contains: str | None = None,
        method_in: list[str] | None = None,
        status_in: list[int] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Snapshot the current Charles session and inspect only new entries without advancing the live cursor."""
        resolution = _coerce_live_snapshot_format(snapshot_format)
        result = await live_service.read(
            live_session_id=live_session_id,
            snapshot_format=resolution.snapshot_format,
            host_contains=host_contains,
            path_contains=path_contains,
            method_in=method_in,
            status_in=status_in,
            limit=min(limit, config.max_query_limit),
            advance=False,
        )
        return _with_live_snapshot_resolution(result, resolution)

    @mcp.tool()
    async def reverse_read_live_entries(
        live_session_id: str,
        snapshot_format: LiveSnapshotFormatParam = "xml",
        host_contains: str | None = None,
        path_contains: str | None = None,
        method_in: list[str] | None = None,
        status_in: list[int] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Snapshot the current Charles session and advance the live cursor to consume new entries."""
        resolution = _coerce_live_snapshot_format(snapshot_format)
        result = await live_service.read(
            live_session_id=live_session_id,
            snapshot_format=resolution.snapshot_format,
            host_contains=host_contains,
            path_contains=path_contains,
            method_in=method_in,
            status_in=status_in,
            limit=min(limit, config.max_query_limit),
            advance=True,
        )
        return _with_live_snapshot_resolution(result, resolution)

    @mcp.tool()
    async def reverse_stop_live_analysis(
        live_session_id: str,
        restore_recording: bool = True,
    ) -> dict[str, Any]:
        """Stop a reverse live-analysis session and optionally restore Charles recording."""
        return await live_service.stop(
            live_session_id=live_session_id,
            restore_recording=restore_recording,
        )

    @mcp.tool()
    async def reverse_analyze_live_login_flow(
        live_session_id: str,
        snapshot_format: LiveSnapshotFormatParam = "xml",
        host_contains: str | None = None,
        path_keywords: list[str] | None = None,
        limit: int = 20,
        advance: bool = True,
        decode_bodies: bool = True,
        descriptor_path: str | None = None,
        message_type: str | None = None,
        run_replay: bool = False,
        replay_json_overrides: dict[str, Any] | None = None,
        replay_use_proxy: bool = False,
    ) -> dict[str, Any]:
        """Run a task-oriented live login/auth reverse-analysis workflow on new traffic.
        Read summary/report first and expand evidence only as needed."""
        resolution = _coerce_live_snapshot_format(snapshot_format)
        result = await workflow_service.analyze_live_login_flow(
            live_session_id=live_session_id,
            snapshot_format=resolution.snapshot_format,
            host_contains=host_contains,
            path_keywords=path_keywords,
            limit=min(limit, config.max_query_limit),
            advance=advance,
            decode_bodies=decode_bodies,
            descriptor_path=descriptor_path,
            message_type=message_type,
            run_replay=run_replay,
            replay_json_overrides=replay_json_overrides,
            replay_use_proxy=replay_use_proxy,
        )
        return _with_live_snapshot_resolution(result, resolution)

    @mcp.tool()
    async def reverse_analyze_live_api_flow(
        live_session_id: str,
        snapshot_format: LiveSnapshotFormatParam = "xml",
        host_contains: str | None = None,
        path_keywords: list[str] | None = None,
        limit: int = 20,
        advance: bool = True,
        decode_bodies: bool = True,
        descriptor_path: str | None = None,
        message_type: str | None = None,
        run_replay: bool = False,
        replay_json_overrides: dict[str, Any] | None = None,
        replay_use_proxy: bool = False,
    ) -> dict[str, Any]:
        """Run a task-oriented live API reverse-analysis workflow on new traffic.
        Read summary/report first and expand evidence only as needed."""
        resolution = _coerce_live_snapshot_format(snapshot_format)
        result = await workflow_service.analyze_live_api_flow(
            live_session_id=live_session_id,
            snapshot_format=resolution.snapshot_format,
            host_contains=host_contains,
            path_keywords=path_keywords,
            limit=min(limit, config.max_query_limit),
            advance=advance,
            decode_bodies=decode_bodies,
            descriptor_path=descriptor_path,
            message_type=message_type,
            run_replay=run_replay,
            replay_json_overrides=replay_json_overrides,
            replay_use_proxy=replay_use_proxy,
        )
        return _with_live_snapshot_resolution(result, resolution)

    @mcp.tool()
    async def reverse_analyze_live_signature_flow(
        live_session_id: str,
        snapshot_format: LiveSnapshotFormatParam = "xml",
        host_contains: str | None = None,
        path_keywords: list[str] | None = None,
        signature_hints: list[str] | None = None,
        limit: int = 20,
        advance: bool = True,
        decode_bodies: bool = True,
        descriptor_path: str | None = None,
        message_type: str | None = None,
        run_replay: bool = False,
        replay_json_overrides: dict[str, Any] | None = None,
        replay_use_proxy: bool = False,
    ) -> dict[str, Any]:
        """Run a task-oriented live signature reverse-analysis workflow on new traffic.
        Read summary/report first and expand evidence only as needed."""
        resolution = _coerce_live_snapshot_format(snapshot_format)
        result = await workflow_service.analyze_live_signature_flow(
            live_session_id=live_session_id,
            snapshot_format=resolution.snapshot_format,
            host_contains=host_contains,
            path_keywords=path_keywords,
            signature_hints=signature_hints,
            limit=min(limit, config.max_query_limit),
            advance=advance,
            decode_bodies=decode_bodies,
            descriptor_path=descriptor_path,
            message_type=message_type,
            run_replay=run_replay,
            replay_json_overrides=replay_json_overrides,
            replay_use_proxy=replay_use_proxy,
        )
        return _with_live_snapshot_resolution(result, resolution)


def create_server(config: Config | None = None) -> FastMCP:
    """Create a FastMCP server exposing only the reverse-analysis tools."""
    runtime = build_reverse_runtime(config)
    mcp = FastMCP("CharlesMCPReverse", json_response=True)
    register_reverse_tools(mcp, runtime)
    return mcp
