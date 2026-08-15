"""Keyword/trend baseline: a runnable deterministic agent.

Unlike the rare-tag helper (which needs direct corpus access and is used
offline), this baseline operates only through the agent-facing environment
API, so it cannot observe the hidden post-cutoff corpus.
"""

from __future__ import annotations

from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, TerminalOutcome

# Query families ranked by expected keyword density in the toy corpus.
_QUERY_FAMILIES = [
    "evidence grounded hypothesis",
    "falsification counter evidence",
    "research gap generation",
    "temporal evaluation agent",
]


class KeywordTrendBaseline:
    """Search a fixed set of keyword families, read the top hits, and claim the
    best-supported family as a gap. Deterministic and intentionally simple."""

    def run(self, env: CounterGapEnv) -> None:
        read_ids: list[str] = []
        family_hits: dict[str, list[str]] = {}

        for query in _QUERY_FAMILIES:
            result = env.step(Action(
                type=ActionType.SEARCH,
                payload={"query": query, "k": 2},
            ))
            hits = []
            for doc in result["results"][:2]:
                doc_id = doc["document_id"]
                if doc_id not in env.read_ids:
                    env.step(Action(type=ActionType.READ, payload={"document_id": doc_id}))
                    read_ids.append(doc_id)
                hits.append(doc_id)
            family_hits[query] = hits

        best_family = max(family_hits, key=lambda q: len(family_hits[q]))
        best_ids = family_hits[best_family]
        if not best_ids:
            env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop(
                "No keyword family matched any pre-cutoff document.",
            )))
            return

        env.step(Action(
            type=ActionType.PROPOSE_GAP,
            payload={
                "text": (
                    f"Keyword baseline: documents matching '{best_family}' "
                    "form the most supported family, yet no document evaluates "
                    "their combination under a frozen temporal protocol."
                ),
                "evidence_ids": best_ids,
            },
        ))
        env.step(Action(
            type=ActionType.ABANDON_GAP,
            payload={"reason": "Keyword/trend baselines do not establish a terminal gap claim."},
        ))
        env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop(
            "Keyword/trend baseline complete.",
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
                "rationale": "Keyword baselines intentionally terminate without falsification.",
            },
        },
    }
