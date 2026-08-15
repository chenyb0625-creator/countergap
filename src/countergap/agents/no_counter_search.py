from __future__ import annotations

from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, TerminalOutcome


class NoCounterSearchAblation:
    """CounterSearchAgent ablation that stops before falsification search.

    It intentionally shares the full agent's initial retrieval, proposal, and
    follow-up retrieval budget. The only removed capability is the active
    counter-evidence objective and the resulting revision/rejection loop.
    """

    def run(self, env: CounterGapEnv) -> None:
        initial = env.step(Action(
            type=ActionType.SEARCH,
            payload={"query": "research gap evaluation agent", "k": 4},
        ))

        evidence_ids: list[str] = []
        for document in initial["results"][:2]:
            env.step(Action(
                type=ActionType.READ,
                payload={"document_id": document["document_id"]},
            ))
            evidence_ids.append(document["document_id"])

        if not evidence_ids:
            env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop("No initial supporting evidence was retrieved.")))
            return

        env.step(Action(
            type=ActionType.PROPOSE_GAP,
            payload={
                "text": "Research-gap agents may lack explicit falsification by counter-evidence search.",
                "evidence_ids": evidence_ids,
            },
        ))
        env.step(Action(
            type=ActionType.SEARCH,
            payload={
                "query": "explicit falsification research gap agents",
                "k": 4,
                "hypothesis_id": "h0",
            },
        ))
        expansion = env.step(Action(
            type=ActionType.SEARCH,
            payload={"query": "scientific literature evaluation", "k": 4},
        ))
        for document in expansion["results"][:2]:
            document_id = document["document_id"]
            if document_id not in env.read_ids:
                env.step(Action(
                    type=ActionType.READ,
                    payload={"document_id": document_id},
                ))
        env.step(Action(
            type=ActionType.ABANDON_GAP,
            payload={"reason": "The no-counter-search ablation cannot make a terminal gap claim."},
        ))
        env.step(Action(
            type=ActionType.STOP,
            payload=_inconclusive_stop("Counter-search was intentionally disabled for this ablation."),
        ))


def _inconclusive_stop(reason: str) -> dict[str, object]:
    return {
        "reason": reason,
        "outcome": TerminalOutcome.INSUFFICIENT_EVIDENCE.value,
        "stop_decision": {
            "latest_hypothesis_challenged": False,
            "no_unresolved_direct_counterevidence": True,
            "search_saturation": {
                "query_families_attempted": 3,
                "independent_sources_read": 0,
                "new_relevant_docs_last_round": 0,
                "new_counterevidence_last_round": 0,
                "revision_stable_rounds": 0,
                "established": True,
                "rationale": "This ablation intentionally ends without the counter-search capability.",
            },
        },
    }
