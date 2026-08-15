"""Tests for the deterministic non-LLM baselines added after M0."""

from __future__ import annotations

from datetime import date

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.baselines.embedding_boundary import EmbeddingBoundaryBaseline, cosine_similarity, _vectorize
from countergap.baselines.keyword_trend_agent import KeywordTrendBaseline
from countergap.env import CounterGapEnv
from countergap.schemas import ActionType, Document, TerminalOutcome


def docs() -> list[Document]:
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
    return CounterGapEnv(
        backend=LocalFrozenCorpusBackend(docs(), cutoff=cutoff),
        cutoff=cutoff,
        action_budget=budget,
    )


def test_cosine_similarity_symmetric_and_bounded():
    vec = _vectorize("research gap evaluation literature")
    same = cosine_similarity(vec, _vectorize("research gap evaluation literature"))
    assert abs(same - 1.0) < 1e-9
    assert cosine_similarity(vec, _vectorize("completely unrelated physics topic")) < 0.1


def test_keyword_trend_baseline_runs_and_stops():
    env = make_env()
    KeywordTrendBaseline().run(env)
    assert env.stopped
    assert env.terminal_outcome == TerminalOutcome.INSUFFICIENT_EVIDENCE
    assert env.hypothesis is not None and env.hypothesis.status == "abandoned"
    actions = [event.action.type.value for event in env.trace]
    assert ActionType.PROPOSE_GAP.value in actions
    assert "z" not in env.visible_ids


def test_embedding_boundary_baseline_proposes_sparse_document():
    env = make_env()
    EmbeddingBoundaryBaseline().run(env)
    assert env.stopped
    assert env.terminal_outcome == TerminalOutcome.INSUFFICIENT_EVIDENCE
    assert env.hypothesis is not None
    assert env.hypothesis.status == "abandoned"
    # Claim must reference a read document, and the hidden doc stays hidden.
    assert set(env.hypothesis.evidence_ids) <= env.read_ids
    assert "z" not in env.visible_ids
    # Boundary claim text should mention the sparse-neighbourhood rationale.
    assert "sparse semantic neighbourhood" in env.hypothesis.text
