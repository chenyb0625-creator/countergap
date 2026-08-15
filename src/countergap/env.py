from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from countergap.adapters.literature import LiteratureBackend
from countergap.schemas import (
    Action,
    ActionType,
    EvidenceState,
    GapHypothesis,
    RevisionRecord,
    RevisionType,
    StopDecision,
    TerminalOutcome,
    TraceEvent,
)


@dataclass
class CounterGapEnv:
    backend: LiteratureBackend
    cutoff: date
    action_budget: int = 12
    visible_ids: set[str] = field(default_factory=set)
    read_ids: set[str] = field(default_factory=set)
    counter_visible_ids: set[str] = field(default_factory=set)
    counter_read_ids: set[str] = field(default_factory=set)
    hypothesis: GapHypothesis | None = None
    hypothesis_history: list[GapHypothesis] = field(default_factory=list)
    revision_history: list[RevisionRecord] = field(default_factory=list)
    terminal_outcome: TerminalOutcome | None = None
    stop_decision: StopDecision | None = None
    _trace: list[TraceEvent] = field(default_factory=list, init=False, repr=False)
    stopped: bool = False

    @property
    def remaining_budget(self) -> int:
        return max(self.action_budget - len(self._trace), 0)

    @property
    def trace(self) -> tuple[TraceEvent, ...]:
        """Return an immutable snapshot of the append-only action log."""
        return tuple(event.model_copy(deep=True) for event in self._trace)

    def observe(self) -> dict[str, Any]:
        return {
            "remaining_budget": self.remaining_budget,
            "visible_ids": sorted(self.visible_ids),
            "read_ids": sorted(self.read_ids),
            "hypothesis": self.hypothesis.model_dump() if self.hypothesis else None,
            "terminal_outcome": self.terminal_outcome.value if self.terminal_outcome else None,
            "stopped": self.stopped,
        }

    def step(self, action: Action) -> dict[str, Any]:
        if self.stopped:
            raise RuntimeError("Environment already stopped.")
        if self.remaining_budget <= 0:
            raise RuntimeError("Action budget exhausted.")

        exposed_document_ids: list[str] = []

        if action.type in {ActionType.SEARCH, ActionType.SEARCH_COUNTEREVIDENCE}:
            query = str(action.payload.get("query", "")).strip()
            if not query:
                raise ValueError("search action requires non-empty query")
            k = int(action.payload.get("k", 5))
            self._validate_targeted_search(action)
            docs = self.backend.search(query, k=k)
            self._validate_pre_cutoff(docs)
            exposed_document_ids = [document.document_id for document in docs]
            self.visible_ids.update(d.document_id for d in docs)
            self._record_targeted_search(action)
            if action.type == ActionType.SEARCH_COUNTEREVIDENCE:
                self.counter_visible_ids.update(exposed_document_ids)
            result = {"results": [d.model_dump(mode="json") for d in docs]}

        elif action.type == ActionType.READ:
            document_id = str(action.payload.get("document_id", ""))
            if document_id not in self.visible_ids:
                raise PermissionError("Document must be surfaced by search before read.")
            doc = self.backend.read(document_id)
            self._validate_pre_cutoff([doc])
            self.read_ids.add(document_id)
            if document_id in self.counter_visible_ids:
                self.counter_read_ids.add(document_id)
            result = {"document": doc.model_dump(mode="json")}

        elif action.type == ActionType.PROPOSE_GAP:
            text = str(action.payload.get("text", "")).strip()
            evidence_ids = list(action.payload.get("evidence_ids", []))
            if not text:
                raise ValueError("propose_gap requires text")
            if not set(evidence_ids).issubset(self.read_ids):
                raise ValueError("Gap evidence must reference documents already read.")
            self.hypothesis = GapHypothesis(
                hypothesis_id=f"h{len(self.hypothesis_history)}",
                text=text,
                evidence_ids=evidence_ids,
            )
            self.hypothesis_history.append(self.hypothesis)
            result = {"hypothesis": self.hypothesis.model_dump()}

        elif action.type == ActionType.REVISE_GAP:
            if self.hypothesis is None:
                raise RuntimeError("No active hypothesis to revise.")
            text = str(action.payload.get("text", "")).strip()
            reason = str(action.payload.get("reason", "")).strip()
            evidence_ids = list(action.payload.get("evidence_ids", self.hypothesis.evidence_ids))
            counterevidence_ids = list(action.payload.get("counterevidence_ids", []))
            trigger_document_ids = list(action.payload.get("trigger_document_ids", []))
            changed_dimensions = list(action.payload.get("changed_dimensions", []))
            if not text:
                raise ValueError("revise_gap requires text")
            if not reason:
                raise ValueError("revise_gap requires a reason")
            if not set(evidence_ids).issubset(self.read_ids):
                raise ValueError("Revised evidence must reference documents already read.")
            if not set(counterevidence_ids).issubset(self.counter_read_ids):
                raise ValueError("Revision counterevidence must be read after a counter-search.")
            if set(evidence_ids).intersection(counterevidence_ids):
                raise ValueError("Supporting and counterevidence IDs must not overlap.")
            if not trigger_document_ids or not set(trigger_document_ids).issubset(counterevidence_ids):
                raise ValueError("Revision triggers must identify counterevidence documents.")
            if not changed_dimensions:
                raise ValueError("Revision requires changed dimensions.")
            try:
                revision_type = RevisionType(action.payload["revision_type"])
            except KeyError as error:
                raise ValueError("Revision requires a revision_type") from error
            previous_hypothesis_id = self.hypothesis.hypothesis_id
            self.hypothesis.counterevidence_ids = counterevidence_ids
            self.hypothesis = GapHypothesis(
                hypothesis_id=f"h{len(self.hypothesis_history)}",
                text=text,
                evidence_ids=evidence_ids,
                status="active",
                revision=self.hypothesis.revision + 1,
            )
            self.hypothesis_history.append(self.hypothesis)
            self.revision_history.append(RevisionRecord(
                from_hypothesis_id=previous_hypothesis_id,
                to_hypothesis_id=self.hypothesis.hypothesis_id,
                revision_type=revision_type,
                trigger_document_ids=trigger_document_ids,
                changed_dimensions=changed_dimensions,
                specificity_increase=action.payload.get("specificity_increase"),
            ))
            result = {"hypothesis": self.hypothesis.model_dump(), "reason": reason}

        elif action.type == ActionType.REJECT_GAP:
            if self.hypothesis is None:
                raise RuntimeError("No active hypothesis to reject.")
            reason = str(action.payload.get("reason", "")).strip()
            counterevidence_ids = list(action.payload.get("counterevidence_ids", []))
            if not reason:
                raise ValueError("reject_gap requires a reason")
            if not counterevidence_ids:
                raise ValueError("reject_gap requires counterevidence IDs")
            if not set(counterevidence_ids).issubset(self.counter_read_ids):
                raise ValueError("Rejected evidence must be read after a counter-search.")
            self.hypothesis.counterevidence_ids = counterevidence_ids
            self.hypothesis.status = "rejected"
            result = {"reason": reason}

        elif action.type == ActionType.ABANDON_GAP:
            if self.hypothesis is None or self.hypothesis.status != "active":
                raise RuntimeError("No active hypothesis to abandon.")
            reason = str(action.payload.get("reason", "")).strip()
            if not reason:
                raise ValueError("abandon_gap requires a reason")
            self.hypothesis.status = "abandoned"
            result = {"reason": reason}

        elif action.type == ActionType.STOP:
            reason = str(action.payload.get("reason", "")).strip()
            if not reason:
                raise ValueError("stop requires a reason")
            try:
                outcome = TerminalOutcome(action.payload["outcome"])
            except KeyError as error:
                raise ValueError("stop requires an explicit terminal outcome") from error
            decision = StopDecision.model_validate(action.payload.get("stop_decision", {}))
            self._validate_stop(outcome, decision, action.payload)
            self.stopped = True
            self.terminal_outcome = outcome
            self.stop_decision = decision
            result = {"reason": reason, "outcome": outcome.value}

        else:
            raise ValueError(f"Unsupported action: {action.type}")

        event = TraceEvent(
            step=len(self._trace),
            action=action.model_copy(deep=True),
            observation_summary={
                "remaining_budget_after": max(self.remaining_budget - 1, 0),
                "visible_count": len(self.visible_ids),
                "read_count": len(self.read_ids),
            },
            exposed_document_ids=exposed_document_ids,
        )
        self._trace.append(event)
        return result

    def _validate_pre_cutoff(self, documents: list[Any]) -> None:
        if any(document.publication_date > self.cutoff for document in documents):
            raise RuntimeError("Backend attempted to expose a post-cutoff document.")

    def evidence_state(self) -> EvidenceState:
        latest = self.hypothesis
        return EvidenceState(
            retrieved_document_ids=sorted(self.visible_ids),
            exposed_document_ids=sorted(self.visible_ids),
            read_document_ids=sorted(self.read_ids),
            supporting_evidence_ids=list(latest.evidence_ids) if latest else [],
            counterevidence_ids=list(latest.counterevidence_ids) if latest else [],
            final_claim_evidence_ids=list(latest.final_claim_evidence_ids) if latest else [],
        )

    def _record_targeted_search(self, action: Action) -> None:
        self._validate_targeted_search(action)
        target_id = str(action.payload.get("hypothesis_id", "")).strip()
        if not target_id:
            return
        if action.type == ActionType.SEARCH_COUNTEREVIDENCE:
            self.hypothesis.counter_search_count += 1
        else:
            self.hypothesis.targeted_search_count += 1
        self.hypothesis.terminal_eligible = (
            self.hypothesis.targeted_search_count >= 1
            and self.hypothesis.counter_search_count >= 1
        )

    def _validate_targeted_search(self, action: Action) -> None:
        target_id = str(action.payload.get("hypothesis_id", "")).strip()
        if action.type == ActionType.SEARCH_COUNTEREVIDENCE and self.hypothesis and not target_id:
            raise ValueError("counter-search requires a target hypothesis_id")
        if not target_id:
            return
        if self.hypothesis is None or self.hypothesis.status != "active":
            raise RuntimeError("Targeted search requires an active hypothesis.")
        if target_id != self.hypothesis.hypothesis_id:
            raise ValueError("Targeted search must target the active hypothesis.")

    def _validate_stop(
        self,
        outcome: TerminalOutcome,
        decision: StopDecision,
        payload: dict[str, Any],
    ) -> None:
        if self.remaining_budget > 1 and not decision.search_saturation.established:
            raise RuntimeError("Stop with remaining budget requires search saturation evidence.")

        if self.hypothesis and self.hypothesis.status == "active":
            if not self.hypothesis.terminal_eligible or not decision.latest_hypothesis_challenged:
                raise RuntimeError("Final hypothesis has not been challenged.")
            if not decision.no_unresolved_direct_counterevidence:
                raise RuntimeError("Stop requires resolving direct counterevidence.")

        if outcome == TerminalOutcome.VALIDATED_CANDIDATE_GAP:
            if self.hypothesis is None or self.hypothesis.status != "active":
                raise RuntimeError("Validated outcome requires an active hypothesis.")
            final_ids = list(payload.get("final_claim_evidence_ids", []))
            if not final_ids:
                raise ValueError("Validated final hypothesis requires claim-specific evidence.")
            if not set(final_ids).issubset(self.read_ids):
                raise ValueError("Final claim evidence must reference documents already read.")
            self.hypothesis.final_claim_evidence_ids = final_ids
            self.hypothesis.status = "validated"

        if outcome == TerminalOutcome.NO_VALIDATED_GAP:
            if self.hypothesis is not None and self.hypothesis.status != "rejected":
                raise RuntimeError("No-gap outcome requires a rejected hypothesis or no candidate.")
