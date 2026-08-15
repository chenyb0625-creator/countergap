from datetime import date

import pytest

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.agents.counter_search import CounterSearchAgent
from countergap.agents.no_counter_search import NoCounterSearchAblation
from countergap.baselines.random_agent import RandomBaseline
from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, Document


CUTOFF = date(2022, 12, 31)


def make_env(action_budget: int = 12) -> CounterGapEnv:
    document = Document(
        document_id="pre",
        title="Agent research evaluation gap counter evidence literature discovery",
        abstract="A pre-cutoff document for deterministic environment tests.",
        publication_date=CUTOFF,
        domain="test",
    )
    return CounterGapEnv(
        backend=LocalFrozenCorpusBackend([document], cutoff=CUTOFF),
        cutoff=CUTOFF,
        action_budget=action_budget,
    )


def test_budget_decreases_and_exhaustion_preserves_trace():
    env = make_env(action_budget=1)

    env.step(Action(type=ActionType.SEARCH, payload={"query": "agent"}))

    assert env.remaining_budget == 0
    assert len(env.trace) == 1
    with pytest.raises(RuntimeError, match="budget exhausted"):
        env.step(Action(type=ActionType.STOP))
    assert len(env.trace) == 1


def test_invalid_action_is_rejected_without_recording_an_event():
    env = make_env()

    with pytest.raises(ValueError, match="non-empty query"):
        env.step(Action(type=ActionType.SEARCH, payload={"query": " "}))

    assert env.remaining_budget == 12
    assert env.trace == ()


def test_gap_revision_requires_an_explicit_reason():
    env = make_env()
    env.step(Action(type=ActionType.SEARCH, payload={"query": "agent"}))
    env.step(Action(type=ActionType.READ, payload={"document_id": "pre"}))
    env.step(Action(
        type=ActionType.PROPOSE_GAP,
        payload={"text": "A candidate gap.", "evidence_ids": ["pre"]},
    ))

    with pytest.raises(ValueError, match="requires a reason"):
        env.step(Action(
            type=ActionType.REVISE_GAP,
            payload={"text": "A revised candidate.", "evidence_ids": ["pre"]},
        ))

    assert len(env.trace) == 3
    assert env.hypothesis is not None
    assert env.hypothesis.revision == 0


def test_trace_is_append_only_and_externally_immutable():
    env = make_env()
    env.step(Action(type=ActionType.SEARCH, payload={"query": "agent"}))
    initial_event = env.trace[0]

    env.step(Action(type=ActionType.READ, payload={"document_id": "pre"}))

    assert [event.step for event in env.trace] == [0, 1]
    assert env.trace[0] == initial_event
    with pytest.raises(AttributeError):
        env.trace.append(initial_event)

    exported_trace = env.trace
    exported_trace[0].action.payload["query"] = "mutated"
    assert env.trace[0].action.payload["query"] == "agent"


def test_random_baseline_is_deterministic_for_the_same_seed_and_config():
    first = make_env()
    second = make_env()

    RandomBaseline(seed=7).run(first)
    RandomBaseline(seed=7).run(second)

    def signature(env: CounterGapEnv) -> list[tuple[int, ActionType, dict[str, object]]]:
        return [
            (event.step, event.action.type, event.action.payload)
            for event in env.trace
        ]

    assert signature(first) == signature(second)
    assert first.hypothesis == second.hypothesis


def test_no_counter_search_ablation_removes_only_falsification_loop():
    full = make_env()
    ablated = make_env()

    CounterSearchAgent().run(full)
    NoCounterSearchAblation().run(ablated)

    full_initial = [event.action for event in full.trace[:3]]
    ablated_initial = [event.action for event in ablated.trace[:3]]
    assert full_initial == ablated_initial
    assert any(
        event.action.type == ActionType.SEARCH_COUNTEREVIDENCE
        for event in full.trace
    )
    assert all(
        event.action.type != ActionType.SEARCH_COUNTEREVIDENCE
        for event in ablated.trace
    )
    full_retrievals = [
        event.action for event in full.trace
        if event.action.type in {ActionType.SEARCH, ActionType.SEARCH_COUNTEREVIDENCE}
    ]
    ablated_retrievals = [
        event.action for event in ablated.trace
        if event.action.type in {ActionType.SEARCH, ActionType.SEARCH_COUNTEREVIDENCE}
    ]
    assert len(full_retrievals) == len(ablated_retrievals) == 3
    assert [action.payload["k"] for action in full_retrievals] == [4, 4, 4]
    assert [action.payload["k"] for action in ablated_retrievals] == [4, 4, 4]
    assert all(
        event.action.type not in {ActionType.REVISE_GAP, ActionType.REJECT_GAP}
        for event in ablated.trace
    )
    assert ablated.hypothesis is not None
    assert ablated.hypothesis.revision == 0
    assert ablated.hypothesis.status == "abandoned"
    assert ablated.remaining_budget >= 0
