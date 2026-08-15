"""Deterministic offline scoring proxy for completed CounterGap traces.

This is NOT a human review. It computes every score component from an explicit,
auditable formula over the trace and the frozen corpus, then writes an
``offline_evaluation`` record with ``evaluator_id="countergap_auto_v1"`` so it
cannot be mistaken for manual inspection. Per AGENTS.md §8, claims still
require manual trace inspection.

Formulas (documented in the record's notes):
- pre_cutoff_novelty   = 1 - max over pre-cutoff docs of Jaccard(claim, doc)
- evidence_quality     = mean over final-claim evidence docs of Jaccard(claim, doc)
- counterevidence_robustness: validated + revision -> 0.9; validated -> 0.8;
  rejected (falsified) -> 1.0; otherwise 0.3
- future_emergence     = max over post-cutoff docs of Jaccard(claim, doc)
  (imperfect corroboration signal only, never ground truth)
- reproducibility      = 1.0 for seeded/deterministic methods, 0.5 for LLM
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from countergap.evaluation.runner import write_offline_evaluation
from countergap.schemas import (
    Document,
    FutureEmergenceStatus,
    OfflineEvaluation,
    ReviewEvidenceState,
    ReviewVerdict,
    ScoreVector,
    TerminalAssessment,
    TerminalOutcome,
)

_NON_DETERMINISTIC = {"one_shot_llm", "llm_counter_search"}


def _terms(text: str) -> set[str]:
    return {w for w in text.lower().split() if len(w) > 3}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _claim_text(summary: dict) -> str:
    for key in ("final_hypothesis", "last_hypothesis"):
        hypothesis = summary.get(key)
        if hypothesis and hypothesis.get("text"):
            return str(hypothesis["text"])
    return ""


def _claim_evidence_ids(summary: dict) -> list[str]:
    hypothesis = summary.get("final_hypothesis") or summary.get("last_hypothesis")
    if not hypothesis:
        return []
    ids = hypothesis.get("final_claim_evidence_ids") or hypothesis.get("evidence_ids") or []
    return [str(x) for x in ids]


def _read_ids(summary: dict) -> set[str]:
    evidence = summary.get("evidence_state") or {}
    return {str(x) for x in evidence.get("read_document_ids", [])}


def _remaining_budget(trace_records: list[dict]) -> int:
    for record in reversed(trace_records):
        if record.get("record_type") == "action":
            obs = record.get("event", {}).get("observation_summary", {})
            if "remaining_budget_after" in obs:
                return int(obs["remaining_budget_after"])
    return 0


def score_trace(
    trace_path: Path,
    corpus_docs: list[Document],
    cutoff: date,
) -> OfflineEvaluation:
    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    run_id = records[0]["run_id"]
    summary = records[-1]["summary"]
    method = records[0]["metadata"]["method_name"]
    terminal = summary.get("terminal_outcome")

    pre_docs = [d for d in corpus_docs if d.publication_date <= cutoff]
    post_docs = [d for d in corpus_docs if d.publication_date > cutoff]

    claim = _terms(_claim_text(summary))
    evidence_ids = _claim_evidence_ids(summary)
    read_ids = _read_ids(summary)
    by_id = {d.document_id: d for d in corpus_docs}

    novelty = 1.0 - max((_jaccard(claim, _terms(f"{d.title} {d.abstract}")) for d in pre_docs), default=0.0)
    if not claim:
        novelty = 0.5
    quality_docs = [by_id[x] for x in evidence_ids if x in by_id]
    evidence_quality = (
        sum(_jaccard(claim, _terms(f"{d.title} {d.abstract}")) for d in quality_docs) / len(quality_docs)
        if quality_docs else 0.0
    )

    if terminal == TerminalOutcome.VALIDATED_CANDIDATE_GAP.value:
        robustness = 0.9 if summary.get("revision_history") else 0.8
        verdict = ReviewVerdict.VALIDATED_CANDIDATE_GAP
    elif terminal == TerminalOutcome.NO_VALIDATED_GAP.value:
        robustness = 1.0  # successful falsification: the counter-search worked
        verdict = ReviewVerdict.NO_VALIDATED_GAP
    else:
        robustness = 0.3
        verdict = ReviewVerdict.INSUFFICIENT_VALIDATION

    emergence = max((_jaccard(claim, _terms(f"{d.title} {d.abstract}")) for d in post_docs), default=0.0) if claim else 0.0
    if not claim:
        status = FutureEmergenceStatus.NOT_APPLICABLE
        emergence = None
        emergence_note = "No claim text was produced; future emergence is not applicable."
    elif emergence >= 0.5:
        status = FutureEmergenceStatus.EVALUATED_POSITIVE
        emergence_note = "Automated term-overlap with post-cutoff corpus; imperfect corroboration only."
    elif emergence > 0.0:
        status = FutureEmergenceStatus.UNCERTAIN
        emergence_note = "Weak automated term-overlap with post-cutoff corpus; needs manual review."
    else:
        status = FutureEmergenceStatus.EVALUATED_NEGATIVE
        emergence_note = "No automated term-overlap with post-cutoff corpus."

    reproducibility = 0.5 if method in _NON_DETERMINISTIC else 1.0

    stop_decision = summary.get("stop_decision") or {}
    saturation = stop_decision.get("search_saturation") or {}
    terminal_assessment = TerminalAssessment(
        final_hypothesis_challenged=bool(stop_decision.get("latest_hypothesis_challenged")),
        search_saturation_established=bool(saturation.get("established")),
        premature_stop=not bool(saturation.get("established")),
        remaining_budget=_remaining_budget(records),
    )

    hypothesis = summary.get("final_hypothesis") or summary.get("last_hypothesis") or {}
    evidence = ReviewEvidenceState(
        retrieved_document_ids=list((summary.get("evidence_state") or {}).get("retrieved_document_ids", [])),
        read_document_ids=sorted(read_ids),
        supporting_evidence_ids=[str(x) for x in hypothesis.get("evidence_ids", [])],
        counterevidence_ids=[str(x) for x in hypothesis.get("counterevidence_ids", [])],
        final_claim_evidence_ids=[str(x) for x in hypothesis.get("final_claim_evidence_ids", [])],
    )

    return OfflineEvaluation(
        run_id=run_id,
        evaluator_id="countergap_auto_v1",
        rubric_version="v2-auto",
        score_vector=ScoreVector(
            pre_cutoff_novelty=novelty,
            evidence_quality=evidence_quality,
            counterevidence_robustness=robustness,
            future_emergence=emergence,
            reproducibility=reproducibility,
        ),
        future_emergence_status=status,
        future_emergence_note=emergence_note,
        evidence=evidence,
        future_evidence_ids=[d.document_id for d in post_docs],
        terminal_assessment=terminal_assessment,
        verdict=verdict,
        notes=[
            "Provisional automated rubric (countergap_auto_v1); NOT a human review.",
            "novelty = 1 - max Jaccard(claim, pre-cutoff doc); evidence_quality = mean Jaccard over claim evidence docs.",
            "counterevidence_robustness: validated+revision=0.9, validated=0.8, falsified=1.0, else=0.3.",
            "future_emergence is automated term overlap only; it is an imperfect offline corroboration signal, never truth.",
            f"reproducibility: {'0.5 (LLM sampling; multi-seed check required)' if method in _NON_DETERMINISTIC else '1.0 (deterministic method)'}.",
            "Manual trace inspection is still required before any scientific claim (AGENTS.md §8).",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, nargs="+", required=True)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data" / "demo_corpus.jsonl")
    parser.add_argument("--cutoff", default="2022-12-31")
    args = parser.parse_args()

    cutoff = date.fromisoformat(args.cutoff)
    corpus_docs = [
        Document.model_validate_json(line)
        for line in args.corpus.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = []
    for trace_path in args.trace:
        evaluation = score_trace(trace_path, corpus_docs, cutoff)
        output = write_offline_evaluation(
            trace_path, evaluation, trace_path.with_name(f"{trace_path.stem}.evaluation.jsonl"),
        )
        results.append({"trace": str(trace_path), "evaluation": str(output)})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
