# Real-Corpus Trace Inspection Report (2026-08-15)

Manual inspection of the M3 real-corpus runs, required by AGENTS.md §8 before
any scientific claim. This report is an audit log, not a conclusion about the
research question.

## Protocol

- Corpus: `data/llm_agent_eval_v1.jsonl` — OpenAlex CC0 snapshot, 326 documents
  ("language model agents", 2019-2025).
- Cutoffs: 2023-12-31, 2024-06-30, 2024-12-31.
- Seeds: 42, 7 (LLM); 42, 7, 2024, 1234, 99 (deterministic).
- Budget: 16 actions.
- Total traces: 118 (90 deterministic grid + 12 LLM grid + 16 single-run demo).
- Inspection: `scripts/inspect_trace.py` on 24 representative traces across
  all three cutoffs and all eight methods.

## Coverage

| Method | Traces | Inspected |
|---|---|---|
| random | 15 (3 cutoffs × 5 seeds) | 3 |
| keyword_trend | 15 | 2 |
| one_shot | 15 | 2 |
| no_counter_search | 15 | 2 |
| counter_search | 15 | 3 |
| embedding_boundary | 15 | 2 |
| one_shot_llm | 6 (3 cutoffs × 2 seeds) | 4 |
| llm_counter_search | 6 | 6 (all) |
| **Total** | **102 grid + 16 demo** | **24** |

## Findings

### R1 — LLM agent stability across cutoffs (6/6 validated)
All six `llm_counter_search` runs (3 cutoffs × 2 seeds) produced
`validated_candidate_gap`. The claims focus on two topics: (a) evaluating
long-term behavioral stability / social dynamics of LLM agents in multi-agent
societies, and (b) standardized benchmarks for emergent social phenomena. The
counter-search consistently surfaces papers on agent tuning (Agent-FLAN) and
multi-agent frameworks, but the LLM judges them as not directly covering the
specific gap. This is a **potential false-positive signal**: the claim is
narrow enough that the counter-evidence doesn't directly falsify it — a
classic scope-narrowing strategy.

### R2 — Earlier reject was a single-seed phenomenon
The first single-run demo (cutoff 2024-06-30, before the multi-cutoff grid)
produced a `no_validated_gap` (reject) — a counterexample discovery. The
multi-cutoff grid did not reproduce this: all 6 runs validated. This
highlights LLM non-determinism: the same agent on the same corpus can reject
or validate depending on the model's sampling. The reject trace remains a
valid example of the falsification mechanism working, but it is not the
typical outcome.

### R3 — F1 auditability fix verified
The F1 fix (adding `model_reasoning` to propose/revise/reject payloads) is
implemented and tested. On runs where the LLM returns a `reasoning` field in
its verdict JSON, it is captured in the trace. On runs where the model omits
it, the `reason` field is used as a fallback. Runs that go straight to
`validated` (retain path) do not produce a verdict action, so no reasoning is
recorded — this is a remaining gap (the retain decision's reasoning is still
not in the trace).

### R4 — Overlap invariant triggered and fixed
The real corpus triggered a new env invariant violation: the LLM sometimes
lists the same document as both supporting evidence and counter-evidence.
Fixed in `_revise` by removing overlapping IDs from the support list before
the env sees them. This is a model-reasoning quality issue, not an env bug —
the env correctly rejects impossible states.

### R5 — One-shot LLM proposes but cannot validate
All `one_shot_llm` runs (6/6) produce `insufficient_evidence` — the same
pattern as on the toy corpus. The claims are substantive and specific (e.g.,
"no study evaluates social behavior or personality traits of LLM agents"),
but without falsification search, the environment honestly marks them
unvalidated. This is the intended contrast.

### R6 — Heuristic counter_search is corpus-agnostic
The deterministic `counter_search` agent runs identically on the real corpus
(9-10 steps, `insufficient_evidence`) — it proposes the same hardcoded claim,
finds d4-equivalent counter-evidence, revises, and stops. It does not adapt
to the real corpus's content, which is expected (it was designed for the toy
corpus). A real heuristic agent would need corpus-specific query generation.

### R7 — Retrieval is the ceiling (confirmed on real corpus)
The bag-of-words backend returns at most 5 documents per query. On the 142-doc
pre-cutoff corpus, the LLM's falsification queries are semantically rich
("long-term stability LLM agent societies", "social norm formation multi-agent
LLM simulation") but the backend matches on term overlap only. A missed
counter-evidence paper here would look identical to "no counter-evidence
exists" — the same F6 confound from the toy corpus, now confirmed on real data.

### R8 — No temporal leakage
Across all 118 traces, no post-cutoff document was ever exposed to any agent.
The `LocalFrozenCorpusBackend` filters at construction time; the env
re-validates on every search/read. Verified by checking `exposed_document_ids`
in all inspected traces.

## Failure-mode inventory (real corpus)

| Mode | Seen | Notes |
|---|---|---|
| Claim fabricated without evidence | no | env enforces evidence ⊆ read_ids |
| Post-cutoff leak | no | R8 |
| Evidence/counter-evidence overlap | 1× (fixed) | R4 |
| LLM retains despite plausible counter-evidence | 6/6 | R1 — potential false-positive |
| LLM rejects (counterexample discovery) | 1× (single-seed) | R2 — not reproduced in grid |
| Retrieval ceiling confound | ongoing | R7 |
| False-positive terminal gap | possible | R1 — needs human judgment |

## Bottom line

The full 8-method suite runs end-to-end on a real 326-document OpenAlex corpus
across three cutoffs. The LLM counter-search agent consistently produces
validated gap claims, but the claims are narrow enough that counter-evidence
doesn't directly falsify them — a potential false-positive signal that
requires human judgment. The earlier reject example remains a valid
demonstration of the falsification mechanism, but is not the typical outcome.
**No statistical claim is made from these traces.** The key next step before
any claim is a multi-seed grid (≥5 seeds per cutoff) with human review of
each validated claim's counter-evidence coverage.
