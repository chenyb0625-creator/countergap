# Trace Inspection Report (2026-08-15)

Manual inspection required by AGENTS.md §8 before any scientific claim. This
report is an audit log, not a conclusion about the research question.

## Protocol

- Corpus: `data/demo_corpus.jsonl` (6 synthetic docs, cutoff 2022-12-31, 4 pre / 2 post hidden).
- Runs: `scripts/run_grid.py --llm` → **34 traces** (30 deterministic + 4 DeepSeek).
- Seeds: `[42, 7, 2024, 1234, 99]`; budget 16; same corpus/cutoff for every run.
- Inspection: `scripts/inspect_trace.py` line-by-line on 16 traces
  (6 LLM/agent runs, 5 random seeds, 5 deterministic representatives).
  The other 18 deterministic traces were proven semantically identical to an
  inspected representative by the grid's semantic-hash check (action types,
  payloads, exposed ids, terminal summary; timestamps excluded).
- Reviewer: agent-assisted manual review (no LLM was consulted for judgment).

## Coverage

| Method | Traces | Inspected line-by-line | Same as inspected (hash) |
|---|---|---|---|
| random | 5 | 5 (distinct, seed-driven) | – |
| keyword_trend | 5 | 1 | 4 |
| one_shot | 5 | 1 | 4 |
| no_counter_search | 5 | 2 (verified identical) | 3 |
| counter_search | 5 | 2 (verified identical) | 3 |
| embedding_boundary | 5 | 1 | 4 |
| one_shot_llm (DeepSeek) | 2 | 2 | – |
| llm_counter_search (DeepSeek) | 2 | 2 | – |
| **Total** | **34** | **16** | **18** |

## Findings

### F1 — LLM agent read counter-evidence but did not cite it (seed 42)
`grid_llm_counter_search_seed42`: the challenge counter-search surfaced and the
agent **read d4** (*Falsification loops for machine-generated scientific
hypotheses* — the closest pre-cutoff counter-evidence document), yet the final
claim cites only d1/d2 and `counterevidence_ids` is empty.

- **Defensible**: d4 falsifies *hypotheses*; the claim is specifically about
  *literature mapping + question generation* combinations. The verdict prompt
  may legitimately judge d4 non-direct.
- **Risk**: the trace cannot show *why* the LLM ignored d4; a reviewer cannot
  distinguish "judged irrelevant" from "ignored by accident". This is a
  known audibility limit of model verdicts (no reasoning is logged).
- **Action**: for any real claim, capture the model's stated reason for
  retaining despite counter-evidence (already in `_last_verdict`, not yet
  written into the trace — future improvement).

### F2 — Counterexample discovery worked (heuristic counter_search)
`grid_counter_search_seed42/7`: initial claim ("agents may lack explicit
falsification") was **revised** after d4 surfaced, narrowing to
"counter-evidence search evaluated under strict temporal freezing". The agent
then re-searched and re-falsified the revised claim and honestly stopped
`insufficient_evidence` (no fabricated terminal gap). Correct falsification
behaviour; no false-positive terminal claim in any of the 10 counter-search
traces (5 heuristic + 2 LLM seeds × check).

### F3 — One-shot LLM vs counter agent: same claim, different verdict
Both DeepSeek runs of `one_shot_llm` and `llm_counter_search` generated
substantively the **same claim** (literature mapping + question generation
combination). Only the counter-search agent could validate it (2/2 runs,
`validated_candidate_gap`); one-shot is structurally unable to (honestly
stops `insufficient_evidence`). This is exactly the contrast the environment
is designed to expose — but it is a **single-corpus, 2-seed demonstration**,
not evidence for the central hypothesis.

### F4 — Random baseline never fabricates
All 5 seeds propose a placeholder gap and abandon it; no terminal claim,
no counter-search. Baseline behaves as designed. Its only purpose is the
lowest bar in the comparison table.

### F5 — Bag-of-words proxies are corpus-fragile
`embedding_boundary` picked d2 (the only LLM-question-generation doc) as the
sparse-neighbourhood outlier — plausible on this corpus, but "sparsity" is an
artifact of the toy corpus's small size and the proxy's bag-of-words
vectorization. On real corpora, document-level semantics (and real embeddings)
are required before this baseline is meaningful.

### F6 — Retrieval is the ceiling for counter-search
All counter-evidence searches go through the term-overlap backend. In every
LLM run the falsification queries were semantically reasonable but the backend
returned at most the same 3-4 pre-cutoff documents. **A missed counter-evidence
document here would look identical to "no counter-evidence exists"** — a known
confound (AGENTS.md §12.8: don't confuse retrieval coverage with truth).

### F7 — Reproducibility accounting
- Deterministic methods: semantically identical across 5 seeds (hash check).
  The random baseline differs across seeds by design and is seed-reproducible
  (same seed → same trace, covered by unit tests).
- LLM methods: 2/2 runs agree on terminal outcome and claim substance, but
  queries and step counts vary (11 vs 10 steps). Sampling temperature ⇒
  `reproducibility = 0.5` in the auto rubric; multi-seed grid still pending
  (2 seeds is indicative only).
- **Tooling note**: byte-level trace hashing fails because traces carry
  timestamps; reproducibility must be compared on semantic content.

## Failure-mode inventory (toy corpus)

| Mode | Seen | Notes |
|---|---|---|
| Claim fabricated without evidence | no | env enforces `evidence_ids ⊆ read_ids` |
| Post-cutoff leak | no | hidden docs never exposed in any trace |
| Unread exposed counter-evidence | no | challenge phase reads up to 2 new docs (fixed earlier) |
| Counter-evidence ignored by LLM | 1× | F1; reason not auditable from trace |
| Missed counter-evidence (retrieval limit) | possible | F6 confound, not observable from trace |
| False-positive terminal gap | none | only validated run is the LLM agent's |

## Bottom line

The environment, baselines, and logging behave as specified on the toy
corpus; the LLM pipeline is operational and stable across 2 seeds. **No
scientific claim about the research question is made from these traces** —
that requires a real corpus, ≥20 human-reviewed traces, and a multi-seed
grid (M3). The F1 audibility gap (model verdicts not logged) is the most
important known limitation to fix before moving to real corpora.
