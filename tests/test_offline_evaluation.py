import json
from datetime import date

import pytest

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.env import CounterGapEnv
from countergap.evaluation.runner import write_offline_evaluation, write_run_trace
from countergap.schemas import (
    Action,
    ActionType,
    Document,
    FutureEmergenceStatus,
    OfflineEvaluation,
    ReviewVerdict,
    RunMetadata,
    TerminalOutcome,
)


def completed_trace(tmp_path):
    cutoff = date(2022, 12, 31)
    document = Document(
        document_id="pre",
        title="Pre-cutoff document",
        abstract="",
        publication_date=cutoff,
        domain="test",
    )
    env = CounterGapEnv(
        backend=LocalFrozenCorpusBackend([document], cutoff=cutoff),
        cutoff=cutoff,
        action_budget=2,
    )
    env.step(Action(type=ActionType.STOP, payload={
        "reason": "complete",
        "outcome": TerminalOutcome.INSUFFICIENT_EVIDENCE.value,
        "stop_decision": {
            "latest_hypothesis_challenged": False,
            "no_unresolved_direct_counterevidence": True,
            "search_saturation": {
                "query_families_attempted": 0,
                "independent_sources_read": 0,
                "new_relevant_docs_last_round": 0,
                "new_counterevidence_last_round": 0,
                "revision_stable_rounds": 0,
                "established": True,
                "rationale": "Fixture terminates without a candidate hypothesis.",
            },
        },
    }))
    trace = tmp_path / "run.jsonl"
    write_run_trace(
        env,
        RunMetadata(
            run_id="run-1",
            seed=3,
            corpus_version="test-v1",
            cutoff=cutoff,
            method_name="test",
            action_budget=2,
        ),
        trace,
    )
    return trace


def assessment(run_id: str = "run-1") -> OfflineEvaluation:
    return OfflineEvaluation.model_validate({
        "run_id": run_id,
        "evaluator_id": "reviewer-1",
        "score_vector": {
            "pre_cutoff_novelty": 0.6,
            "evidence_quality": 0.7,
            "counterevidence_robustness": 0.8,
            "future_emergence": None,
            "reproducibility": 1.0,
        },
        "future_emergence_status": FutureEmergenceStatus.NOT_EVALUATED.value,
        "future_emergence_note": "No post-cutoff corpus was supplied for this fixture.",
        "evidence": {
            "retrieved_document_ids": ["pre"],
            "read_document_ids": ["pre"],
            "supporting_evidence_ids": ["pre"],
            "counterevidence_ids": [],
            "final_claim_evidence_ids": [],
        },
        "terminal_assessment": {
            "final_hypothesis_challenged": False,
            "search_saturation_established": True,
            "premature_stop": False,
            "remaining_budget": 1,
        },
        "verdict": ReviewVerdict.INSUFFICIENT_VALIDATION.value,
        "notes": ["Manual review of the toy trace."],
    })


def test_offline_evaluation_is_linked_to_run_without_modifying_trace(tmp_path):
    trace = completed_trace(tmp_path)
    before = trace.read_text(encoding="utf-8")

    output = write_offline_evaluation(trace, assessment(), tmp_path / "evaluation.jsonl")
    record = json.loads(output.read_text(encoding="utf-8"))

    assert trace.read_text(encoding="utf-8") == before
    assert record["record_type"] == "offline_evaluation"
    assert record["run_id"] == "run-1"
    assert record["evaluation"]["future_evidence_ids"] == []
    assert record["evaluation"]["score_vector"]["future_emergence"] is None
    assert record["aggregate_score"] == pytest.approx(0.7352941176470589)


def test_offline_evaluation_rejects_run_id_mismatch(tmp_path):
    trace = completed_trace(tmp_path)

    with pytest.raises(ValueError, match="run_id"):
        write_offline_evaluation(trace, assessment("other-run"), tmp_path / "evaluation.jsonl")
