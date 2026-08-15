"""Embedding-boundary baseline (M1): semantic sparse-neighbourhood heuristic.

The README spec says an *embedding* boundary baseline belongs here once
embeddings are introduced. Until then this implementation uses a transparent
bag-of-words cosine-similarity proxy computed entirely with the stdlib, so the
baseline remains runnable with zero new dependencies and no vector database.

Idea: a topic whose documents sit in a sparse neighbourhood (low maximum
cosine similarity to every other read document) is a candidate gap — the
literature around it is thin.

The baseline operates only through the agent-facing environment API
(search/read/propose/stop), so it cannot observe the hidden post-cutoff
corpus. This is deliberately a *proxy*: real embedding models would replace
`_vectorize` without touching the agent loop.
"""

from __future__ import annotations

import math
import re

from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, Document, TerminalOutcome

_QUERY_FAMILIES = [
    "research gap evaluation",
    "evidence grounded hypothesis",
    "falsification counter evidence",
    "temporal evaluation agent",
    "literature mapping review",
]


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2]


def _vectorize(text: str) -> dict[str, float]:
    counts: dict[str, float] = {}
    for token in _tokens(text):
        counts[token] = counts.get(token, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {token: count / norm for token, count in counts.items()}


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
    return sum(v * larger.get(token, 0.0) for token, v in smaller.items())


class EmbeddingBoundaryBaseline:
    """Search several query families, read the hits, and claim the document
    with the thinnest semantic neighbourhood (lowest max-cosine to other read
    documents) as a candidate gap."""

    def run(self, env: CounterGapEnv) -> None:
        read_docs: list[Document] = []
        for query in _QUERY_FAMILIES:
            # Reserve 3 actions for propose + abandon + stop.
            if env.remaining_budget <= 3:
                break
            result = env.step(Action(
                type=ActionType.SEARCH,
                payload={"query": query, "k": 2},
            ))
            for doc in result["results"][:1]:
                if doc["document_id"] not in env.read_ids and env.remaining_budget > 3:
                    env.step(Action(type=ActionType.READ, payload={"document_id": doc["document_id"]}))
                    read_docs.append(Document.model_validate(doc))

        if len(read_docs) < 2:
            env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop(
                "Too few documents read to estimate neighbourhood sparsity.",
            )))
            return

        vectors = [(doc, _vectorize(f"{doc.title} {doc.abstract}")) for doc in read_docs]
        boundary_scores: list[tuple[float, Document]] = []
        for doc, vec in vectors:
            neighbours = [cosine_similarity(vec, other) for other_doc, other in vectors if other_doc != doc]
            boundary_scores.append((1.0 - max(neighbours), doc))
        boundary_scores.sort(key=lambda pair: (-pair[0], pair[1].document_id))
        sparsity, outlier = boundary_scores[0]

        env.step(Action(
            type=ActionType.PROPOSE_GAP,
            payload={
                "text": (
                    f"Embedding-boundary baseline: document '{outlier.title}' sits in a "
                    "sparse semantic neighbourhood, suggesting the surrounding topic is "
                    "under-explored in the frozen corpus."
                ),
                "evidence_ids": [outlier.document_id],
            },
        ))
        env.step(Action(
            type=ActionType.ABANDON_GAP,
            payload={"reason": "Embedding-boundary baselines do not establish a terminal gap claim."},
        ))
        env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop(
            "Embedding-boundary baseline complete.",
        )))


def _inconclusive_stop(reason: str) -> dict[str, object]:
    return {
        "reason": reason,
        "outcome": TerminalOutcome.INSUFFICIENT_EVIDENCE.value,
        "stop_decision": {
            "latest_hypothesis_challenged": False,
            "no_unresolved_direct_counterevidence": True,
            "search_saturation": {
                "query_families_attempted": len(_QUERY_FAMILIES),
                "independent_sources_read": 0,
                "new_relevant_docs_last_round": 0,
                "new_counterevidence_last_round": 0,
                "revision_stable_rounds": 0,
                "established": True,
                "rationale": "Embedding-boundary baselines terminate without falsification.",
            },
        },
    }
