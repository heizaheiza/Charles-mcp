"""Backward-compatible re-export shim for the workflow service.

The real implementation now lives in `charles_mcp.reverse.services.workflows`
as a base class plus three strategy classes (login / api / signature).
This module re-exports `WorkflowService` so existing imports like

    from charles_mcp.reverse.services.workflow_service import WorkflowService

continue to work unchanged.
"""

from __future__ import annotations

from charles_mcp.reverse.services.workflows import WorkflowService

__all__ = ["WorkflowService"]
