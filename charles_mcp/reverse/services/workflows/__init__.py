"""Live reverse-analysis workflow strategies.

`WorkflowService` is a thin facade that wires three strategy classes
(`LoginWorkflow`, `ApiWorkflow`, `SignatureWorkflow`) behind the original
`analyze_live_*_flow` methods. The previous monolithic implementation
lived in `workflow_service.py` and has been kept there as a re-export
shim for backward compatibility.
"""

from __future__ import annotations

from typing import Any

from charles_mcp.reverse.services.decode_service import DecodeService
from charles_mcp.reverse.services.live_analysis_service import LiveAnalysisService
from charles_mcp.reverse.services.query_service import QueryService
from charles_mcp.reverse.services.replay_service import ReplayService
from charles_mcp.reverse.services.workflows.api import ApiWorkflow
from charles_mcp.reverse.services.workflows.login import LoginWorkflow
from charles_mcp.reverse.services.workflows.signature import SignatureWorkflow


class WorkflowService:
    """Compose low-level tools into task-oriented reverse-analysis workflows."""

    def __init__(
        self,
        *,
        live_service: LiveAnalysisService,
        query_service: QueryService,
        decode_service: DecodeService,
        replay_service: ReplayService,
    ) -> None:
        self.live_service = live_service
        self.query_service = query_service
        self.decode_service = decode_service
        self.replay_service = replay_service
        # Pass services as explicit keyword arguments so mypy preserves
        # parameter types through each strategy constructor. Routing them
        # via a generic dict (**deps) would erase the per-key types.
        self._login_workflow = LoginWorkflow(
            live_service=live_service,
            query_service=query_service,
            decode_service=decode_service,
            replay_service=replay_service,
        )
        self._api_workflow = ApiWorkflow(
            live_service=live_service,
            query_service=query_service,
            decode_service=decode_service,
            replay_service=replay_service,
        )
        self._signature_workflow = SignatureWorkflow(
            live_service=live_service,
            query_service=query_service,
            decode_service=decode_service,
            replay_service=replay_service,
        )

    async def analyze_live_login_flow(self, **kwargs: Any) -> dict[str, Any]:
        return await self._login_workflow.run(**kwargs)

    async def analyze_live_api_flow(self, **kwargs: Any) -> dict[str, Any]:
        return await self._api_workflow.run(**kwargs)

    async def analyze_live_signature_flow(self, **kwargs: Any) -> dict[str, Any]:
        return await self._signature_workflow.run(**kwargs)


__all__ = [
    "WorkflowService",
    "LoginWorkflow",
    "ApiWorkflow",
    "SignatureWorkflow",
]
