"""End-to-end tests for LLM-driven methods using a scripted fake model.

No network calls are made; the fake client returns scripted JSON so the agent
trajectories are deterministic.
"""

from __future__ import annotations

from datetime import date

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.agents.llm_counter_search import LLMCounterSearchAgent
from countergap.baselines.one_shot_llm import OneShotLLMBaseline
from countergap.env import CounterGapEnv
from countergap.schemas import ActionType, Document, TerminalOutcome


class FakeLLM:
    """Returns scripted replies in order; defaults to a retain verdict."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[str] = []

    def complete(self, system: str, user: str, **kwargs) -> str:
        self.calls.append(user)
        if self.replies:
            return self.replies.pop(0)
        return '{"decision": "retain", "evidence_ids": ["a"], "final_claim_evidence_ids": ["a"]}'


def corpus_docs() -> list[Document]:
    return [
        Document(
            document_id="a",
            title="Research gap evaluation for literature agents",
            abstract="An agent evaluates research gaps from scientific abstracts.",
            publication_date=date(2021, 6, 1),
            domain="test",
        ),
        Document(
            document_id="b",
            title="Question generation with language models",
            abstract="Language models generate research questions from abstracts.",
            publication_date=date(2021, 9, 1),
            domain="test",
        ),
        Document(
            document_id="c",
            title="Falsification loops for generated hypotheses",
            abstract="Candidate hypotheses are challenged with counter-evidence retrieval.",
            publication_date=date(2022, 11, 1),
            domain="test",
        ),
        Document(
            document_id="z",
            title="Hidden future benchmark",
            abstract="Post-cutoff document that must never be observed.",
            publication_date=date(2024, 1, 1),
            domain="test",
        ),
    ]


def make_env(budget: int = 16) -> CounterGapEnv:
    cutoff = date(2022, 12, 31)
    docs = corpus_docs()
    return CounterGapEnv(
        backend=LocalFrozenCorpusBackend(docs, cutoff=cutoff),
        cutoff=cutoff,
        action_budget=budget,
    )


def test_one_shot_llm_baseline_proposes_and_stops_inconclusive():
    llm = FakeLLM(['{"gap": "Gap claim from model.", "evidence_ids": ["a", "b"]}'])
    env = make_env()
    OneShotLLMBaseline(llm=llm).run(env)

    assert env.stopped
    assert env.terminal_outcome == TerminalOutcome.INSUFFICIENT_EVIDENCE
    actions = [event.action.type.value for event in env.trace]
    assert ActionType.PROPOSE_GAP.value in actions
    assert env.hypothesis is not None and env.hypothesis.status == "abandoned"
    assert set(env.hypothesis.evidence_ids) <= env.read_ids
    # The hidden post-cutoff document must never be observed.
    assert "z" not in env.visible_ids


def test_one_shot_llm_handles_model_failure_gracefully():
    class FailingLLM:
        def complete(self, system, user, **kwargs):  # noqa: ARG002
            raise RuntimeError("boom")

    env = make_env()
    OneShotLLMBaseline(llm=FailingLLM()).run(env)
    assert env.stopped
    assert env.terminal_outcome == TerminalOutcome.INSUFFICIENT_EVIDENCE
    assert "z" not in env.visible_ids


def test_llm_counter_search_validates_surviving_gap():
    llm = FakeLLM([
        '{"gap": "No frozen-corpus evaluation of counter-evidence search for gap claims.", "evidence_ids": ["a", "b"]}',
        '{"queries": ["counter evidence falsification", "temporal evaluation"]}',
        '{"decision": "retain", "evidence_ids": ["a", "b"], "final_claim_evidence_ids": ["a", "b"]}',
    ])
    env = make_env()
    LLMCounterSearchAgent(llm=llm).run(env)

    assert env.stopped
    assert env.terminal_outcome == TerminalOutcome.VALIDATED_CANDIDATE_GAP
    assert env.hypothesis is not None
    assert env.hypothesis.status == "validated"
    assert set(env.hypothesis.final_claim_evidence_ids) <= env.read_ids
    assert env.hypothesis.terminal_eligible
    assert "z" not in env.visible_ids
    # The counter-evidence search must have happened on the final hypothesis.
    assert env.hypothesis.counter_search_count >= 1
    assert env.hypothesis.targeted_search_count >= 1


def test_llm_counter_search_rejects_when_falsified():
    llm = FakeLLM([
        '{"gap": "Claim that prior work already covers.", "evidence_ids": ["a"]}',
        '{"queries": ["counter evidence falsification", "hypothesis generation"]}',
        '{"decision": "reject", "reason": "Prior work falsifies this claim.", "counterevidence_ids": ["c"]}',
    ])
    env = make_env()
    LLMCounterSearchAgent(llm=llm).run(env)

    assert env.stopped
    assert env.terminal_outcome == TerminalOutcome.NO_VALIDATED_GAP
    assert env.hypothesis is not None and env.hypothesis.status == "rejected"
    assert "z" not in env.visible_ids
