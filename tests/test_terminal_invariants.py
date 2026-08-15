from datetime import date

import pytest

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, Document, TerminalOutcome


CUTOFF = date(2022, 12, 31)


def make_env() -> CounterGapEnv:
    documents = [
        Document(
            document_id="support",
            title="Research gap agents",
            abstract="Candidate generation for research gaps.",
            publication_date=CUTOFF,
            domain="test",
        ),
        Document(
            document_id="counter",
            title="Explicit falsification of research gap agents",
            abstract="Prior work applies falsification to research-gap agents.",
            publication_date=CUTOFF,
            domain="test",
        ),
    ]
    return CounterGapEnv(
        backend=LocalFrozenCorpusBackend(documents, cutoff=CUTOFF),
        cutoff=CUTOFF,
        action_budget=12,
    )


def stop_payload(outcome: TerminalOutcome) -> dict[str, object]:
    return {
        "reason": "Evidence-based stopping decision.",
        "outcome": outcome.value,
        "stop_decision": {
            "latest_hypothesis_challenged": True,
            "no_unresolved_direct_counterevidence": True,
            "search_saturation": {
                "query_families_attempted": 2,
                "independent_sources_read": 2,
                "new_relevant_docs_last_round": 0,
                "new_counterevidence_last_round": 0,
                "revision_stable_rounds": 1,
                "established": True,
                "rationale": "The final targeted search families yielded no new evidence.",
            },
        },
    }


def propose_and_revise(env: CounterGapEnv) -> None:
    env.step(Action(type=ActionType.SEARCH, payload={"query": "research gap agents"}))
    env.step(Action(type=ActionType.READ, payload={"document_id": "support"}))
    env.step(Action(type=ActionType.PROPOSE_GAP, payload={
        "text": "Research-gap agents lack falsification.",
        "evidence_ids": ["support"],
    }))
    env.step(Action(type=ActionType.SEARCH_COUNTEREVIDENCE, payload={
        "query": "explicit falsification",
        "hypothesis_id": "h0",
    }))
    env.step(Action(type=ActionType.READ, payload={"document_id": "counter"}))
    env.step(Action(type=ActionType.REVISE_GAP, payload={
        "text": "Research-gap agents may lack temporal evaluation.",
        "evidence_ids": [],
        "counterevidence_ids": ["counter"],
        "reason": "A pre-cutoff paper explicitly applies falsification.",
        "revision_type": "scope_narrowing",
        "trigger_document_ids": ["counter"],
        "changed_dimensions": ["temporal_constraint"],
    }))


def test_revision_resets_validation_and_blocks_direct_stop():
    env = make_env()
    propose_and_revise(env)

    assert env.hypothesis is not None
    assert env.hypothesis.hypothesis_id == "h1"
    assert env.hypothesis.targeted_search_count == 0
    assert env.hypothesis.counter_search_count == 0
    assert env.hypothesis.terminal_eligible is False
    with pytest.raises(RuntimeError, match="Final hypothesis has not been challenged"):
        env.step(Action(type=ActionType.STOP, payload=stop_payload(
            TerminalOutcome.INSUFFICIENT_EVIDENCE,
        )))


def test_revised_hypothesis_requires_targeted_search_and_counter_search():
    env = make_env()
    propose_and_revise(env)
    env.step(Action(type=ActionType.SEARCH, payload={
        "query": "temporal evaluation",
        "hypothesis_id": "h1",
    }))
    env.step(Action(type=ActionType.SEARCH_COUNTEREVIDENCE, payload={
        "query": "temporal evaluation counterevidence",
        "hypothesis_id": "h1",
    }))
    env.step(Action(type=ActionType.STOP, payload=stop_payload(
        TerminalOutcome.INSUFFICIENT_EVIDENCE,
    )))

    assert env.stopped is True
    assert env.terminal_outcome == TerminalOutcome.INSUFFICIENT_EVIDENCE


def test_exposure_does_not_make_unread_document_supporting_evidence():
    env = make_env()
    env.step(Action(type=ActionType.SEARCH, payload={"query": "falsification"}))

    with pytest.raises(ValueError, match="already read"):
        env.step(Action(type=ActionType.PROPOSE_GAP, payload={
            "text": "Unsupported candidate.",
            "evidence_ids": ["counter"],
        }))
    assert env.evidence_state().supporting_evidence_ids == []


def test_no_validated_gap_is_a_valid_terminal_outcome():
    env = make_env()
    env.step(Action(type=ActionType.SEARCH, payload={"query": "research gap agents"}))
    env.step(Action(type=ActionType.READ, payload={"document_id": "support"}))
    env.step(Action(type=ActionType.PROPOSE_GAP, payload={
        "text": "Research-gap agents lack falsification.",
        "evidence_ids": ["support"],
    }))
    env.step(Action(type=ActionType.SEARCH_COUNTEREVIDENCE, payload={
        "query": "explicit falsification",
        "hypothesis_id": "h0",
    }))
    env.step(Action(type=ActionType.READ, payload={"document_id": "counter"}))
    env.step(Action(type=ActionType.REJECT_GAP, payload={
        "reason": "Direct pre-cutoff counterevidence defeats the candidate.",
        "counterevidence_ids": ["counter"],
    }))
    env.step(Action(type=ActionType.STOP, payload=stop_payload(
        TerminalOutcome.NO_VALIDATED_GAP,
    )))

    assert env.stopped is True
    assert env.terminal_outcome == TerminalOutcome.NO_VALIDATED_GAP
    assert env.hypothesis is not None
    assert env.hypothesis.status == "rejected"


def test_stop_with_remaining_budget_requires_saturation_evidence():
    env = make_env()
    payload = stop_payload(TerminalOutcome.INSUFFICIENT_EVIDENCE)
    payload["stop_decision"]["search_saturation"]["established"] = False

    with pytest.raises(RuntimeError, match="saturation evidence"):
        env.step(Action(type=ActionType.STOP, payload=payload))
