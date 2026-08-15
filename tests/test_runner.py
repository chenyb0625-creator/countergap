import json
from datetime import date

import pytest

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.env import CounterGapEnv
from countergap.evaluation.runner import write_run_trace
from countergap.schemas import Action, ActionType, Document, RunMetadata, TerminalOutcome


def stop_payload() -> dict[str, object]:
    return {
        "reason": "complete",
        "outcome": TerminalOutcome.INSUFFICIENT_EVIDENCE.value,
        "stop_decision": {
            "latest_hypothesis_challenged": False,
            "no_unresolved_direct_counterevidence": True,
            "search_saturation": {
                "query_families_attempted": 1,
                "independent_sources_read": 0,
                "new_relevant_docs_last_round": 0,
                "new_counterevidence_last_round": 0,
                "revision_stable_rounds": 0,
                "established": True,
                "rationale": "No candidate hypothesis was proposed.",
            },
        },
    }


def make_env() -> CounterGapEnv:
    cutoff = date(2022, 12, 31)
    document = Document(
        document_id="pre",
        title="Auditable pre-cutoff document",
        abstract="",
        publication_date=cutoff,
        domain="test",
    )
    return CounterGapEnv(
        backend=LocalFrozenCorpusBackend([document], cutoff=cutoff),
        cutoff=cutoff,
        action_budget=3,
    )


def metadata() -> RunMetadata:
    return RunMetadata(
        run_id="test-run",
        seed=7,
        corpus_version="test-v1",
        cutoff=date(2022, 12, 31),
        method_name="test-agent",
        action_budget=3,
    )


def test_completed_run_trace_records_metadata_actions_and_summary(tmp_path):
    env = make_env()
    env.step(Action(type=ActionType.SEARCH, payload={"query": "auditable"}))
    env.step(Action(type=ActionType.STOP, payload=stop_payload()))

    output = write_run_trace(env, metadata(), tmp_path / "trace.jsonl")
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert [record["record_type"] for record in records] == [
        "run_start", "action", "action", "run_end",
    ]
    assert records[0]["metadata"]["cutoff"] == "2022-12-31"
    assert records[1]["event"]["exposed_document_ids"] == ["pre"]
    assert records[-1]["summary"]["stop_reason"] == "complete"
    assert records[-1]["summary"]["score_vector"] is None
    assert records[-1]["summary"]["scoring_status"] == "pending_offline_evaluation"
    assert {record["run_id"] for record in records} == {"test-run"}


def test_runner_rejects_incomplete_or_mislabelled_runs(tmp_path):
    env = make_env()
    with pytest.raises(ValueError, match="completed runs"):
        write_run_trace(env, metadata(), tmp_path / "incomplete.jsonl")

    env.step(Action(type=ActionType.STOP, payload=stop_payload()))
    mismatched = metadata().model_copy(update={"cutoff": date(2023, 1, 1)})
    with pytest.raises(ValueError, match="cutoff"):
        write_run_trace(env, mismatched, tmp_path / "mismatched.jsonl")
