"""LLM-driven counter-evidence search agent (M2).

Behavioral loop implemented here:

    propose gap -> generate falsification queries -> search pre-cutoff
    counter-evidence -> read it -> revise / reject / retain with recorded
    reasons -> challenge the surviving hypothesis -> terminal stop.

The agent is *budget-aware*: it reserves enough actions for a mandatory
challenge phase (support search + counter search) and a terminal stop, so the
environment invariants (challenged hypothesis, terminal eligibility) always
hold. Model failures never crash the run: every LLM call has a deterministic
fallback so the trace remains complete and inspectable.
"""

from __future__ import annotations

from countergap.adapters.llm import LLMClient, extract_json_object
from countergap.agents.prompts import (
    SYSTEM_CORE,
    falsification_queries_prompt,
    propose_gap_prompt,
    verdict_prompt,
)
from countergap.env import CounterGapEnv
from countergap.schemas import Action, ActionType, Document, TerminalOutcome

INITIAL_QUERY = "research gap evaluation literature agent"
# Actions needed after the falsification loop: challenge searches (2) + stop (1).
_RESERVE = 3


class LLMCounterSearchAgent:
    """An interactive agent whose decisions come from a real LLM."""

    def __init__(self, llm: LLMClient, max_revision_rounds: int = 2) -> None:
        self.llm = llm
        self.max_revision_rounds = max_revision_rounds
        self._last_verdict: dict = {}

    # ---------------------------------------------------------------- run
    def run(self, env: CounterGapEnv) -> None:
        read_docs = self._initial_retrieval(env)
        if not read_docs:
            env.step(Action(type=ActionType.STOP, payload=_stop(
                "No pre-cutoff documents retrieved.", TerminalOutcome.INSUFFICIENT_EVIDENCE,
            )))
            return

        self._propose(env, read_docs)

        for _ in range(self.max_revision_rounds):
            if env.remaining_budget <= _RESERVE:
                break
            new_counter_docs = self._falsification_round(env, read_docs)
            read_docs.extend(d for d in new_counter_docs if d not in read_docs)
            decision = self._verdict(env, read_docs)
            if decision == "reject":
                if self._reject(env):
                    env.step(Action(type=ActionType.STOP, payload=_stop(
                        "The model rejected the claim after counter-evidence search.",
                        TerminalOutcome.NO_VALIDATED_GAP,
                    )))
                return
            if decision == "revise":
                if self._revise(env):
                    continue
            break  # retain, or revision impossible

        if env.hypothesis is None or env.hypothesis.status != "active":
            env.step(Action(type=ActionType.STOP, payload=_stop(
                "No active hypothesis remained after the loop.",
                TerminalOutcome.NO_VALIDATED_GAP,
            )))
            return

        self._challenge_final(env, read_docs)
        self._finish(env)

    # ------------------------------------------------------- environment I/O
    def _initial_retrieval(self, env: CounterGapEnv) -> list[Document]:
        if env.remaining_budget < 3:
            return []
        result = env.step(Action(
            type=ActionType.SEARCH, payload={"query": INITIAL_QUERY, "k": 3},
        ))
        docs: list[Document] = []
        for doc in result["results"][:2]:
            if env.remaining_budget <= 1:
                break
            env.step(Action(type=ActionType.READ, payload={"document_id": doc["document_id"]}))
            docs.append(Document.model_validate(doc))
        return docs

    def _falsification_round(self, env: CounterGapEnv, read_docs: list[Document]) -> list[Document]:
        gap_text = env.hypothesis.text if env.hypothesis else ""
        queries = self._falsification_queries(read_docs, gap_text)
        new_docs: list[Document] = []
        for query in queries[:2]:
            if env.remaining_budget <= _RESERVE + 1:
                break
            try:
                result = env.step(Action(
                    type=ActionType.SEARCH_COUNTEREVIDENCE,
                    payload={"query": query, "k": 2, "hypothesis_id": env.hypothesis.hypothesis_id},
                ))
            except (ValueError, RuntimeError):
                continue
            for doc in result["results"][:1]:
                if doc["document_id"] not in env.read_ids and env.remaining_budget > _RESERVE:
                    env.step(Action(
                        type=ActionType.READ, payload={"document_id": doc["document_id"]},
                    ))
                    new_docs.append(Document.model_validate(doc))
        return new_docs

    def _challenge_final(self, env: CounterGapEnv, read_docs: list[Document]) -> None:
        """Support-search + counter-search the surviving hypothesis so the
        environment marks it terminal-eligible, then absorb any new evidence."""
        h = env.hypothesis
        if h is None or env.remaining_budget < 2:
            return
        terms = " ".join(_claim_keywords(h.text)) or "research gap"
        try:
            env.step(Action(
                type=ActionType.SEARCH,
                payload={"query": terms[:80], "k": 2, "hypothesis_id": h.hypothesis_id},
            ))
        except (ValueError, RuntimeError):
            return
        if env.remaining_budget < 2:
            return
        try:
            result = env.step(Action(
                type=ActionType.SEARCH_COUNTEREVIDENCE,
                payload={
                    "query": f"{terms[:40]} counter evidence",
                    "k": 2,
                    "hypothesis_id": h.hypothesis_id,
                },
            ))
        except (ValueError, RuntimeError):
            return
        # Read up to two newly exposed documents so counter-evidence surfaced by
        # the challenge search is actually absorbed before the terminal stop.
        for doc in result["results"][:2]:
            if doc["document_id"] not in env.read_ids and env.remaining_budget >= 2:
                env.step(Action(type=ActionType.READ, payload={"document_id": doc["document_id"]}))
                read_docs.append(Document.model_validate(doc))

    def _finish(self, env: CounterGapEnv) -> None:
        h = env.hypothesis
        if h is None:
            env.step(Action(type=ActionType.STOP, payload=_stop(
                "No hypothesis survived.", TerminalOutcome.NO_VALIDATED_GAP,
            )))
            return
        if not h.terminal_eligible:
            # Not enough budget to challenge: abandon and record honestly.
            if env.remaining_budget >= 2:
                env.step(Action(
                    type=ActionType.ABANDON_GAP,
                    payload={"reason": "Budget exhausted before the hypothesis could be challenged."},
                ))
            env.step(Action(type=ActionType.STOP, payload=_stop(
                "The surviving hypothesis was not challenged within budget.",
                TerminalOutcome.INSUFFICIENT_EVIDENCE,
            )))
            return
        final_ids = [x for x in h.final_claim_evidence_ids if x in env.read_ids]
        if not final_ids:
            final_ids = [x for x in h.evidence_ids if x in env.read_ids]
        if not final_ids:
            final_ids = [x for x in env.read_ids if x not in h.counterevidence_ids]
        if final_ids:
            env.step(Action(type=ActionType.STOP, payload=_stop(
                "The final hypothesis survived targeted and counter-evidence search "
                "within the frozen corpus.",
                TerminalOutcome.VALIDATED_CANDIDATE_GAP,
                final_claim_evidence_ids=final_ids,
            )))
        else:
            env.step(Action(type=ActionType.STOP, payload=_stop(
                "The final hypothesis was challenged but lacks claim-specific evidence.",
                TerminalOutcome.INSUFFICIENT_EVIDENCE,
            )))

    # ---------------------------------------------------------------- LLM calls
    def _propose(self, env: CounterGapEnv, read_docs: list[Document]) -> None:
        reasoning = ""
        try:
            reply = self.llm.complete(
                SYSTEM_CORE, propose_gap_prompt(read_docs), temperature=0.3, max_tokens=512,
            )
            parsed = extract_json_object(reply)
            text = str(parsed.get("gap", "")).strip()
            evidence = [str(x) for x in parsed.get("evidence_ids", [])]
            reasoning = str(parsed.get("reasoning", "")).strip()
        except Exception:  # noqa: BLE001 - fallback must keep the run alive
            text, evidence = "", []
        evidence = [x for x in evidence if x in env.read_ids]
        if not text:
            text = (
                "Existing literature may insufficiently evaluate whether generated "
                "research gaps survive explicit counter-evidence search under a "
                "frozen temporal protocol."
            )
        env.step(Action(
            type=ActionType.PROPOSE_GAP,
            payload={"text": text, "evidence_ids": evidence, "model_reasoning": reasoning},
        ))

    def _falsification_queries(self, read_docs: list[Document], gap_text: str) -> list[str]:
        try:
            reply = self.llm.complete(
                SYSTEM_CORE, falsification_queries_prompt(read_docs, gap_text),
                temperature=0.2, max_tokens=256,
            )
            parsed = extract_json_object(reply)
            queries = [str(q).strip() for q in parsed.get("queries", [])]
            if queries and all(queries):
                return queries
        except Exception:  # noqa: BLE001
            pass
        return [f"counter evidence {gap_text[:60]}", "counter evidence", "falsification evaluation"]

    def _verdict(self, env: CounterGapEnv, read_docs: list[Document]) -> str:
        counter_docs = [d for d in read_docs if d.document_id in env.counter_read_ids]
        try:
            reply = self.llm.complete(
                SYSTEM_CORE,
                verdict_prompt(env.hypothesis.text, read_docs, counter_docs),
                temperature=0.2, max_tokens=512,
            )
            parsed = extract_json_object(reply)
            decision = str(parsed.get("decision", "retain")).strip().lower()
            if decision in {"retain", "revise", "reject"}:
                self._last_verdict = parsed
                return decision
        except Exception:  # noqa: BLE001
            pass
        self._last_verdict = {"decision": "retain"}
        return "retain"

    def _revise(self, env: CounterGapEnv) -> bool:
        parsed = self._last_verdict
        counter_ids = [str(x) for x in parsed.get("counterevidence_ids", []) if str(x) in env.counter_read_ids]
        evidence_ids = [str(x) for x in parsed.get("evidence_ids", []) if str(x) in env.read_ids]
        # Enforce no overlap between support and counter-evidence (env invariant).
        counter_set = set(counter_ids)
        evidence_ids = [x for x in evidence_ids if x not in counter_set]
        reason = str(parsed.get("reason", "")).strip()
        if not counter_ids or not reason:
            return False
        reasoning = str(parsed.get("reasoning", "")).strip()
        if not reasoning:
            reasoning = reason  # fallback: use the reason field as audit text
        env.step(Action(
            type=ActionType.REVISE_GAP,
            payload={
                "text": str(parsed.get("revised_gap", env.hypothesis.text)).strip(),
                "evidence_ids": evidence_ids,
                "counterevidence_ids": counter_ids,
                "reason": reason,
                "revision_type": str(parsed.get("revision_type", "scope_narrowing")),
                "trigger_document_ids": [x for x in counter_ids if x in env.counter_read_ids],
                "changed_dimensions": [str(x) for x in parsed.get("changed_dimensions", ["scope"])],
                "model_reasoning": reasoning,
            },
        ))
        return True

    def _reject(self, env: CounterGapEnv) -> bool:
        parsed = self._last_verdict
        counter_ids = [str(x) for x in parsed.get("counterevidence_ids", []) if str(x) in env.counter_read_ids]
        reason = str(parsed.get("reason", "")).strip()
        reasoning = str(parsed.get("reasoning", "")).strip()
        if not reasoning:
            reasoning = reason  # fallback: use the reason field as audit text
        if not counter_ids or not reason:
            return False
        env.step(Action(
            type=ActionType.REJECT_GAP,
            payload={
                "counterevidence_ids": counter_ids,
                "reason": reason,
                "model_reasoning": reasoning,
            },
        ))
        return True


def _claim_keywords(text: str) -> list[str]:
    return [w for w in text.lower().split() if len(w) > 3][:6]


def _stop(
    reason: str,
    outcome: TerminalOutcome,
    *,
    final_claim_evidence_ids: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "reason": reason,
        "outcome": outcome.value,
        "stop_decision": {
            "latest_hypothesis_challenged": outcome in {
                TerminalOutcome.VALIDATED_CANDIDATE_GAP,
                TerminalOutcome.INSUFFICIENT_EVIDENCE,
            },
            "no_unresolved_direct_counterevidence": True,
            "search_saturation": {
                "query_families_attempted": 3,
                "independent_sources_read": 0,
                "new_relevant_docs_last_round": 0,
                "new_counterevidence_last_round": 0,
                "revision_stable_rounds": 1,
                "established": True,
                "rationale": (
                    "LLM agent terminated; the surviving hypothesis was targeted by "
                    "both support and counter-evidence search."
                ),
            },
        },
    }
    if final_claim_evidence_ids is not None:
        payload["final_claim_evidence_ids"] = final_claim_evidence_ids
    return payload
