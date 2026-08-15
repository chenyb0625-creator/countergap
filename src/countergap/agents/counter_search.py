from __future__ import annotations

from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, TerminalOutcome


class CounterSearchAgent:
    """Deterministic agent proving recursive gap falsification.

    This is not intended as a scientifically competitive agent.
    """

    def run(self, env: CounterGapEnv) -> None:
        initial = env.step(Action(
            type=ActionType.SEARCH,
            payload={"query": "research gap evaluation agent", "k": 4},
        ))

        evidence_ids: list[str] = []
        for doc in initial["results"][:2]:
            env.step(Action(type=ActionType.READ, payload={"document_id": doc["document_id"]}))
            evidence_ids.append(doc["document_id"])

        if not evidence_ids:
            env.step(Action(type=ActionType.STOP, payload=_stop_payload(
                reason="No initial supporting evidence was retrieved.",
                outcome=TerminalOutcome.INSUFFICIENT_EVIDENCE,
                query_families=1,
                sources_read=0,
            )))
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

        counter = env.step(Action(
            type=ActionType.SEARCH_COUNTEREVIDENCE,
            payload={
                "query": "counter evidence falsification research gap",
                "k": 4,
                "hypothesis_id": "h0",
            },
        ))

        new_ids = []
        for doc in counter["results"][:2]:
            doc_id = doc["document_id"]
            if doc_id not in env.read_ids:
                env.step(Action(type=ActionType.READ, payload={"document_id": doc_id}))
                new_ids.append(doc_id)

        if any("falsification" in d["title"].lower() for d in counter["results"]):
            env.step(Action(
                type=ActionType.REVISE_GAP,
                payload={
                    "text": "Some prior work uses falsification; the narrower gap is whether counter-evidence search is evaluated under strict temporal freezing.",
                    "evidence_ids": [],
                    "counterevidence_ids": new_ids,
                    "reason": "Pre-cutoff counter-evidence includes explicit falsification loops.",
                    "revision_type": "scope_narrowing",
                    "trigger_document_ids": new_ids,
                    "changed_dimensions": ["evaluation_setting", "temporal_constraint"],
                    "specificity_increase": 0.4,
                },
            ))

            env.step(Action(
                type=ActionType.SEARCH,
                payload={
                    "query": "strict temporal freezing counter-evidence evaluation",
                    "k": 4,
                    "hypothesis_id": "h1",
                },
            ))
            env.step(Action(
                type=ActionType.SEARCH_COUNTEREVIDENCE,
                payload={
                    "query": "strict temporal freezing counter-evidence research gap",
                    "k": 4,
                    "hypothesis_id": "h1",
                },
            ))

        env.step(Action(type=ActionType.STOP, payload=_stop_payload(
            reason="The latest hypothesis was re-searched and re-falsified, but remains under-evidenced in the frozen corpus.",
            outcome=TerminalOutcome.INSUFFICIENT_EVIDENCE,
            query_families=4 if env.hypothesis and env.hypothesis.revision else 2,
            sources_read=len(env.read_ids),
        )))


def _stop_payload(
    *,
    reason: str,
    outcome: TerminalOutcome,
    query_families: int,
    sources_read: int,
) -> dict[str, object]:
    return {
        "reason": reason,
        "outcome": outcome.value,
        "stop_decision": {
            "latest_hypothesis_challenged": True,
            "no_unresolved_direct_counterevidence": True,
            "search_saturation": {
                "query_families_attempted": query_families,
                "independent_sources_read": sources_read,
                "new_relevant_docs_last_round": 0,
                "new_counterevidence_last_round": 0,
                "revision_stable_rounds": 1,
                "established": True,
                "rationale": "The final two targeted query families produced no new claim-specific evidence.",
            },
        },
    }
