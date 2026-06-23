"""Base class shared by all live reverse-analysis workflow strategies."""

from __future__ import annotations

from typing import Any

from charles_mcp.reverse.models import CaptureSourceFormat
from charles_mcp.reverse.services.decode_service import DecodeService
from charles_mcp.reverse.services.live_analysis_service import LiveAnalysisService
from charles_mcp.reverse.services.query_service import QueryService
from charles_mcp.reverse.services.replay_service import ReplayService
from charles_mcp.reverse.services.workflows._shared import (
    _build_mutation_plan,
    _build_next_actions,
    _build_replay_report,
    _build_selected_request_summary,
    _build_signature_report,
    _collect_decode_observations,
    _empty_mutation_plan,
    _mutation_plan_overview,
    _mutation_strategy_text,
)


class _BaseLiveWorkflow:
    """Template for live reverse-analysis workflow strategies.

    Subclasses customize behavior through class attributes (workflow_name,
    default_path_keywords, candidate_label, mutation_policy, the various
    headline/overview strings) and by implementing _rank_candidates.

    The shared run() orchestrates: live read -> rank -> _build_workflow_result.
    Subclasses with extra parameters (e.g. SignatureWorkflow's signature_hints)
    accept them as kwargs and forward via _ranking_kwargs / _extra_summary.
    """

    workflow_name: str = ""
    default_path_keywords: tuple[str, ...] = ()
    candidate_label: str = ""

    success_headline_template: str = ""
    success_overview: str = ""

    no_items_headline: str = ""
    no_items_overview: str = ""
    no_items_assessment: str = ""
    no_items_actions: list[str] = []

    no_candidates_headline: str = ""
    no_candidates_overview: str = ""
    no_candidates_assessment: str = ""
    no_candidates_actions: list[str] = []

    summary_count_alias: str | None = None
    evidence_candidates_key: str = "candidates"

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

    # ----- subclass hooks ---------------------------------------------------

    def _rank_candidates(
        self,
        items: list[dict[str, Any]],
        *,
        path_keywords: list[str],
        **extra: Any,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _resolve_path_keywords(self, requested: list[str] | None) -> list[str]:
        return requested or list(self.default_path_keywords)

    def _resolve_mutation_policy(self, **extra: Any) -> dict[str, Any]:
        # Subclasses with policy that depends on runtime kwargs (e.g.
        # signature_hints) override this. Default returns the class-level
        # mutation_policy attribute.
        return getattr(self, "mutation_policy")  # noqa: B009 — explicit lookup

    def _extra_summary(self, **extra: Any) -> dict[str, Any]:
        return {}

    # ----- shared orchestration --------------------------------------------

    async def run(
        self,
        *,
        live_session_id: str,
        snapshot_format: CaptureSourceFormat = CaptureSourceFormat.XML,
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
        **extra: Any,
    ) -> dict[str, Any]:
        resolved_keywords = self._resolve_path_keywords(path_keywords)
        live_result = await self.live_service.read(
            live_session_id=live_session_id,
            snapshot_format=snapshot_format,
            host_contains=host_contains,
            limit=limit,
            advance=advance,
        )
        items = list(live_result["items"])
        candidates = self._rank_candidates(items, path_keywords=resolved_keywords, **extra)
        return await self._build_workflow_result(
            live_session_id=live_session_id,
            live_result=live_result,
            items=items,
            candidates=candidates,
            path_keywords=resolved_keywords,
            descriptor_path=descriptor_path,
            message_type=message_type,
            decode_bodies=decode_bodies,
            run_replay=run_replay,
            replay_json_overrides=replay_json_overrides,
            replay_use_proxy=replay_use_proxy,
            mutation_policy=self._resolve_mutation_policy(**extra),
            extra_summary=self._extra_summary(**extra),
        )

    # ----- shared helpers --------------------------------------------------

    def _safe_decode(
        self,
        *,
        entry_id: str,
        side: str,
        descriptor_path: str | None,
        message_type: str | None,
    ) -> dict[str, Any] | None:
        try:
            return self.decode_service.decode_entry_body(
                entry_id=entry_id,
                side=side,
                descriptor_path=descriptor_path,
                message_type=message_type,
            )
        except Exception as exc:
            return {"entry_id": entry_id, "side": side, "decode_error": str(exc)}

    async def _build_workflow_result(
        self,
        *,
        live_session_id: str,
        live_result: dict[str, Any],
        items: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        path_keywords: list[str],
        descriptor_path: str | None,
        message_type: str | None,
        decode_bodies: bool,
        run_replay: bool,
        replay_json_overrides: dict[str, Any] | None,
        replay_use_proxy: bool,
        mutation_policy: dict[str, Any],
        extra_summary: dict[str, Any],
    ) -> dict[str, Any]:
        workflow_name = self.workflow_name
        evidence_candidates_key = self.evidence_candidates_key
        summary_count_alias = self.summary_count_alias

        if not items:
            empty_plan = _empty_mutation_plan(workflow_name)
            return {
                "live_session_id": live_session_id,
                "capture_id": live_result["capture_id"],
                "analysis_status": "no_new_entries",
                "summary": {
                    "headline": self.no_items_headline,
                    "new_transaction_count": live_result["new_transaction_count"],
                    "items_considered": 0,
                    "candidate_count": 0,
                    "selected_entry_id": None,
                    "signature_candidate_fields": [],
                    "replay_outcome": None,
                    **({summary_count_alias: 0} if summary_count_alias else {}),
                    "mutation_plan_overview": _mutation_plan_overview(empty_plan),
                    **extra_summary,
                },
                "report": {
                    "overview": self.no_items_overview,
                    "candidate_assessment": self.no_items_assessment,
                    "selected_request": None,
                    "decoded_observations": [],
                    "signature_analysis": None,
                    "replay_analysis": None,
                    "mutation_strategy": _mutation_strategy_text(empty_plan),
                    "recommended_next_actions": self.no_items_actions,
                },
                "evidence": {
                    "workflow": workflow_name,
                    "path_keywords": path_keywords,
                    "live_read": live_result,
                    evidence_candidates_key: [],
                    "selected_entry_detail": None,
                    "decoded_request": None,
                    "decoded_response": None,
                    "signature_candidates": None,
                    "replay_result": None,
                    "related_findings": [],
                    "mutation_plan": empty_plan,
                },
            }

        if not candidates:
            empty_plan = _empty_mutation_plan(workflow_name)
            return {
                "live_session_id": live_session_id,
                "capture_id": live_result["capture_id"],
                "analysis_status": f"no_{workflow_name}_candidates",
                "summary": {
                    "headline": self.no_candidates_headline,
                    "new_transaction_count": live_result["new_transaction_count"],
                    "items_considered": len(items),
                    "candidate_count": 0,
                    "selected_entry_id": None,
                    "signature_candidate_fields": [],
                    "replay_outcome": None,
                    **({summary_count_alias: 0} if summary_count_alias else {}),
                    "mutation_plan_overview": _mutation_plan_overview(empty_plan),
                    **extra_summary,
                },
                "report": {
                    "overview": self.no_candidates_overview,
                    "candidate_assessment": self.no_candidates_assessment,
                    "selected_request": None,
                    "decoded_observations": [],
                    "signature_analysis": None,
                    "replay_analysis": None,
                    "mutation_strategy": _mutation_strategy_text(empty_plan),
                    "recommended_next_actions": self.no_candidates_actions,
                },
                "evidence": {
                    "workflow": workflow_name,
                    "path_keywords": path_keywords,
                    "live_read": live_result,
                    evidence_candidates_key: [],
                    "selected_entry_detail": None,
                    "decoded_request": None,
                    "decoded_response": None,
                    "signature_candidates": None,
                    "replay_result": None,
                    "related_findings": [],
                    "mutation_plan": empty_plan,
                },
            }

        selected = candidates[0]
        selected_entry_id = selected["entry_id"]
        selected_detail = self.query_service.get_entry_detail(entry_id=selected_entry_id)
        decoded_request = None
        decoded_response = None
        if decode_bodies:
            decoded_request = self._safe_decode(
                entry_id=selected_entry_id,
                side="request",
                descriptor_path=descriptor_path,
                message_type=message_type,
            )
            decoded_response = self._safe_decode(
                entry_id=selected_entry_id,
                side="response",
                descriptor_path=descriptor_path,
                message_type=message_type,
            )

        compare_ids = [candidate["entry_id"] for candidate in candidates[: min(3, len(candidates))]]
        signature_candidates = None
        if len(compare_ids) >= 2:
            signature_candidates = self.query_service.discover_signature_candidates(entry_ids=compare_ids)

        replay_result = None
        if run_replay:
            replay_result = await self.replay_service.replay_entry(
                entry_id=selected_entry_id,
                json_overrides=replay_json_overrides,
                use_proxy=replay_use_proxy,
            )

        related_findings = self.query_service.list_findings(subject_id=selected_entry_id)
        if replay_result and replay_result.get("run"):
            related_findings.extend(
                self.query_service.list_findings(
                    subject_type="run",
                    subject_id=replay_result["run"]["run_id"],
                )
            )

        signature_fields = []
        if signature_candidates is not None:
            signature_fields = [
                item["field"]
                for item in signature_candidates.get("candidates", [])[:5]
            ]

        replay_outcome = None
        if replay_result is not None:
            replay_outcome = {
                "status": replay_result["run"]["execution_status"],
                "baseline_status": replay_result["run"]["diff_summary"].get("baseline_status"),
                "replay_status": replay_result["run"]["diff_summary"].get("replay_status"),
                "status_changed": replay_result["run"]["diff_summary"].get("status_changed"),
            }

        mutation_plan = _build_mutation_plan(
            workflow_name=workflow_name,
            selected_entry_detail=selected_detail,
            signature_candidates=signature_candidates,
            related_findings=related_findings,
            mutation_policy=mutation_policy,
        )

        return {
            "live_session_id": live_session_id,
            "capture_id": live_result["capture_id"],
            "analysis_status": "ok",
            "summary": {
                "headline": self.success_headline_template.format(
                    method=selected_detail["entry"]["method"],
                    path=selected_detail["entry"]["path"],
                ),
                "new_transaction_count": live_result["new_transaction_count"],
                "items_considered": len(items),
                "candidate_count": len(candidates),
                "selected_entry_id": selected_entry_id,
                "signature_candidate_fields": signature_fields,
                "replay_outcome": replay_outcome,
                **({summary_count_alias: len(candidates)} if summary_count_alias else {}),
                "mutation_plan_overview": _mutation_plan_overview(mutation_plan),
                **extra_summary,
            },
            "report": {
                "overview": self.success_overview,
                "candidate_assessment": (
                    f"Scored {len(candidates)} {self.candidate_label} candidate(s); "
                    f"selected `{selected_entry_id}` with score {selected['score']}."
                ),
                "selected_request": _build_selected_request_summary(candidate=selected, detail=selected_detail),
                "decoded_observations": _collect_decode_observations(
                    decoded_request=decoded_request,
                    decoded_response=decoded_response,
                ),
                "signature_analysis": _build_signature_report(signature_candidates),
                "replay_analysis": _build_replay_report(replay_result),
                "mutation_strategy": _mutation_strategy_text(mutation_plan),
                "recommended_next_actions": _build_next_actions(
                    signature_candidates=signature_candidates,
                    replay_result=replay_result,
                    decoded_request=decoded_request,
                    decoded_response=decoded_response,
                ),
            },
            "evidence": {
                "workflow": workflow_name,
                "path_keywords": path_keywords,
                evidence_candidates_key: candidates,
                "live_read": live_result,
                "selected_entry_detail": selected_detail,
                "decoded_request": decoded_request,
                "decoded_response": decoded_response,
                "signature_candidates": signature_candidates,
                "replay_result": replay_result,
                "related_findings": related_findings,
                "mutation_plan": mutation_plan,
            },
        }
