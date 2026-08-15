"""One-shot LLM baseline (M1): a single-pass gap generation without iteration.

Replaces the deterministic heuristic placeholder with a real model call, while
keeping the environment's terminal invariants: a one-shot pass cannot satisfy
the challenged-hypothesis requirement, so the run honestly terminates with
``INSUFFICIENT_EVIDENCE``.
"""

from __future__ import annotations

from countergap.adapters.literature import LiteratureBackend
from countergap.adapters.llm import LLMClient, extract_json_object
from countergap.agents.prompts import SYSTEM_CORE, propose_gap_prompt
from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, Document, TerminalOutcome

INITIAL_QUERY = "research gap evaluation literature agent"


class OneShotLLMBaseline:
    """Search once, read a few documents, ask the model for one gap claim."""

    def __init__(self, llm: LLMClient, top_k: int = 3) -> None:
        self.llm = llm
        self.top_k = top_k

    def run(self, env: CounterGapEnv) -> None:
        result = env.step(Action(
            type=ActionType.SEARCH,
            payload={"query": INITIAL_QUERY, "k": self.top_k},
        ))
        read_docs: list[Document] = []
        for doc in result["results"][:2]:
            env.step(Action(type=ActionType.READ, payload={"document_id": doc["document_id"]}))
            read_docs.append(_as_document(doc))

        if not read_docs:
            env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop(
                "No pre-cutoff documents matched the initial search.",
            )))
            return

        try:
            reply = self.llm.complete(
                SYSTEM_CORE,
                propose_gap_prompt(read_docs),
                temperature=0.2,
                max_tokens=512,
            )
            parsed = extract_json_object(reply)
            gap_text = str(parsed.get("gap", "")).strip()
            evidence_ids = [str(x) for x in parsed.get("evidence_ids", [])]
        except Exception as error:  # noqa: BLE001 - LLM failures must not crash the run
            env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop(
                f"Model call failed; one-shot run recorded as inconclusive. ({type(error).__name__})",
            )))
            return

        valid_evidence = [doc_id for doc_id in evidence_ids if doc_id in env.read_ids]
        if not gap_text or not valid_evidence:
            env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop(
                "Model reply did not reference read documents; one-shot gap not formed.",
            )))
            return

        env.step(Action(
            type=ActionType.PROPOSE_GAP,
            payload={"text": gap_text, "evidence_ids": valid_evidence},
        ))
        env.step(Action(
            type=ActionType.ABANDON_GAP,
            payload={"reason": "One-shot generation does not challenge the hypothesis with counter-evidence."},
        ))
        env.step(Action(type=ActionType.STOP, payload=_inconclusive_stop(
            "One-shot LLM baseline complete.",
        )))


def _as_document(data: dict) -> Document:
    return Document.model_validate(data)


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
                "rationale": "One-shot baselines intentionally terminate without falsification.",
            },
        },
    }
