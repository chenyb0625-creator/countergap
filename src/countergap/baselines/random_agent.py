from __future__ import annotations

import random

from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, TerminalOutcome


class RandomBaseline:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def run(self, env: CounterGapEnv) -> None:
        queries = ["agent research", "evaluation gap", "counter evidence", "literature discovery"]
        query = self.rng.choice(queries)
        result = env.step(Action(type=ActionType.SEARCH, payload={"query": query, "k": 3}))
        docs = result["results"]
        if docs:
            chosen = self.rng.choice(docs)
            env.step(Action(type=ActionType.READ, payload={"document_id": chosen["document_id"]}))
            env.step(Action(
                type=ActionType.PROPOSE_GAP,
                payload={
                    "text": "Random baseline candidate gap.",
                    "evidence_ids": [chosen["document_id"]],
                },
            ))
            env.step(Action(
                type=ActionType.ABANDON_GAP,
                payload={"reason": "Random selection does not establish a terminal gap claim."},
            ))
        env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop("Random baseline complete.")))


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
                "rationale": "This baseline is intentionally stochastic and non-falsifying.",
            },
        },
    }
