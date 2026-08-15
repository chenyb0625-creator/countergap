from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Document(BaseModel):
    document_id: str
    title: str
    abstract: str
    publication_date: date
    domain: str
    tags: list[str] = Field(default_factory=list)


class ActionType(str, Enum):
    SEARCH = "search"
    READ = "read"
    PROPOSE_GAP = "propose_gap"
    SEARCH_COUNTEREVIDENCE = "search_counterevidence"
    REVISE_GAP = "revise_gap"
    REJECT_GAP = "reject_gap"
    ABANDON_GAP = "abandon_gap"
    STOP = "stop"


class Action(BaseModel):
    type: ActionType
    payload: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    step: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action: Action
    observation_summary: dict[str, Any] = Field(default_factory=dict)
    exposed_document_ids: list[str] = Field(default_factory=list)


class GapHypothesis(BaseModel):
    hypothesis_id: str = "h0"
    text: str
    # evidence_ids is retained as the backward-compatible name for explicit
    # pre-cutoff supporting evidence. Exposure alone never populates it.
    evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    final_claim_evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["active", "validated", "rejected", "abandoned"] = "active"
    revision: int = 0
    targeted_search_count: int = 0
    counter_search_count: int = 0
    terminal_eligible: bool = False


class RevisionType(str, Enum):
    SCOPE_NARROWING = "scope_narrowing"
    SCOPE_BROADENING = "scope_broadening"
    DEFINITION_CHANGE = "definition_change"
    POPULATION_CHANGE = "population_change"
    METHOD_CHANGE = "method_change"
    EVALUATION_SETTING_CHANGE = "evaluation_setting_change"
    TEMPORAL_CONSTRAINT_ADDED = "temporal_constraint_added"
    CLAIM_REJECTION = "claim_rejection"


class RevisionRecord(BaseModel):
    from_hypothesis_id: str
    to_hypothesis_id: str
    revision_type: RevisionType
    trigger_document_ids: list[str] = Field(min_length=1)
    changed_dimensions: list[str] = Field(min_length=1)
    specificity_increase: float | None = Field(default=None, ge=0.0, le=1.0)


class TerminalOutcome(str, Enum):
    VALIDATED_CANDIDATE_GAP = "validated_candidate_gap"
    NO_VALIDATED_GAP = "no_validated_gap"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    SEARCH_BUDGET_EXHAUSTED = "search_budget_exhausted"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class SearchSaturation(BaseModel):
    query_families_attempted: int = Field(ge=0)
    independent_sources_read: int = Field(ge=0)
    new_relevant_docs_last_round: int = Field(ge=0)
    new_counterevidence_last_round: int = Field(ge=0)
    revision_stable_rounds: int = Field(ge=0)
    established: bool
    rationale: str = Field(min_length=1)


class StopDecision(BaseModel):
    latest_hypothesis_challenged: bool
    no_unresolved_direct_counterevidence: bool
    search_saturation: SearchSaturation


class EvidenceState(BaseModel):
    retrieved_document_ids: list[str] = Field(default_factory=list)
    exposed_document_ids: list[str] = Field(default_factory=list)
    read_document_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    final_claim_evidence_ids: list[str] = Field(default_factory=list)


class ScoreVector(BaseModel):
    pre_cutoff_novelty: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    counterevidence_robustness: float = Field(ge=0.0, le=1.0)
    future_emergence: float | None = Field(default=None, ge=0.0, le=1.0)
    reproducibility: float = Field(ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float | None]:
        return self.model_dump()


class RunMetadata(BaseModel):
    run_id: str
    seed: int
    corpus_version: str
    cutoff: date
    method_name: str
    action_budget: int


class RunSummary(BaseModel):
    stop_reason: str
    terminal_outcome: TerminalOutcome | None = None
    final_hypothesis: GapHypothesis | None = None
    last_hypothesis: GapHypothesis | None = None
    hypothesis_history: list[GapHypothesis] = Field(default_factory=list)
    revision_history: list[RevisionRecord] = Field(default_factory=list)
    evidence_state: EvidenceState = Field(default_factory=EvidenceState)
    stop_decision: StopDecision | None = None
    score_vector: ScoreVector | None = None
    aggregate_score: float | None = None
    scoring_status: Literal["pending_offline_evaluation", "completed"] = (
        "pending_offline_evaluation"
    )


class FutureEmergenceStatus(str, Enum):
    EVALUATED_POSITIVE = "evaluated_positive"
    EVALUATED_NEGATIVE = "evaluated_negative"
    UNCERTAIN = "uncertain"
    NOT_EVALUATED = "not_evaluated"
    NOT_APPLICABLE = "not_applicable"


class ReviewVerdict(str, Enum):
    VALIDATED_CANDIDATE_GAP = "validated_candidate_gap"
    NO_VALIDATED_GAP = "no_validated_gap"
    INSUFFICIENT_VALIDATION = "insufficient_validation"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class ReviewEvidenceState(BaseModel):
    retrieved_document_ids: list[str] = Field(default_factory=list)
    read_document_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    final_claim_evidence_ids: list[str] = Field(default_factory=list)


class TerminalAssessment(BaseModel):
    final_hypothesis_challenged: bool
    search_saturation_established: bool
    premature_stop: bool
    remaining_budget: int = Field(ge=0)


class OfflineEvaluation(BaseModel):
    """Reviewer-supplied scoring evidence for a completed run.

    Future evidence may be named here because this model is only consumed after
    the agent environment has stopped; it is never passed into the environment.
    """

    run_id: str
    evaluator_id: str
    rubric_version: str = "v2"
    score_vector: ScoreVector
    future_emergence_status: FutureEmergenceStatus
    future_emergence_note: str = ""
    evidence: ReviewEvidenceState
    future_evidence_ids: list[str] = Field(default_factory=list)
    terminal_assessment: TerminalAssessment
    verdict: ReviewVerdict
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_future_emergence(self) -> "OfflineEvaluation":
        evaluated = {
            FutureEmergenceStatus.EVALUATED_POSITIVE,
            FutureEmergenceStatus.EVALUATED_NEGATIVE,
            FutureEmergenceStatus.UNCERTAIN,
        }
        if self.future_emergence_status in evaluated and self.score_vector.future_emergence is None:
            raise ValueError("Evaluated future emergence requires a numeric score.")
        if self.future_emergence_status in {
            FutureEmergenceStatus.NOT_EVALUATED,
            FutureEmergenceStatus.NOT_APPLICABLE,
        }:
            if self.score_vector.future_emergence is not None:
                raise ValueError("Unevaluated future emergence must be null.")
            if not self.future_emergence_note.strip():
                raise ValueError("Unevaluated future emergence requires an explanatory note.")
        if not set(self.evidence.final_claim_evidence_ids).issubset(
            self.evidence.read_document_ids
        ):
            raise ValueError("Final claim evidence must be a subset of read documents.")
        return self
