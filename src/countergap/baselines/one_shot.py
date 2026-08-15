from __future__ import annotations

from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, TerminalOutcome


class OneShotBaseline:
    """Deterministic heuristic standing in for a future one-shot LLM baseline."""

    def run(self, env: CounterGapEnv) -> None:
        result = env.step(Action(
            type=ActionType.SEARCH,
            payload={"query": "research gap evaluation literature agent", "k": 3},
        ))
        evidence_ids = []
        for doc in result["results"][:2]:
            env.step(Action(type=ActionType.READ, payload={"document_id": doc["document_id"]}))
            evidence_ids.append(doc["document_id"])

        if evidence_ids:
            env.step(Action(
                type=ActionType.PROPOSE_GAP,
                payload={
                    "text": "Existing literature may insufficiently evaluate whether generated research gaps survive explicit counter-evidence search.",
                    "evidence_ids": evidence_ids,
                },
            ))
            env.step(Action(
                type=ActionType.ABANDON_GAP,
                payload={"reason": "One-shot generation does not establish a terminal gap claim."},
            ))
        env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop("One-shot baseline complete.")))


def _inconclusive_stop(reason: str) -> dict[str, object]:
    return {
        "reason": reason,
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
                "rationale": "This baseline is intentionally limited to one search pass.",
            },
        },
    }
