# CounterGap

**Temporal, falsifiable evaluation environment for Research Gap Discovery agents**

CounterGap is a small, reproducible research scaffold for studying a specific question:

> Can an AI research agent identify plausible research gaps from only the literature available before a cutoff date, and can active counter-evidence search reduce false-gap claims?

This repository is intentionally **not** a full scientific assistant, not a generic paper-search product, and not dependent on an unfinished Gap Explorer system. It is a self-contained evaluation environment first. A Gap Explorer adapter can be added later.

---

## 1. Why this project exists

Research-gap generation is easy to demo and hard to evaluate.

A language model can produce a convincing "gap" from a handful of papers, but that does not establish that:

- the gap was actually absent from the pre-cutoff literature;
- the system searched hard enough for counter-evidence;
- the claim survives literature coverage changes;
- the result is better than a keyword/trend heuristic;
- the "discovery" is not just hindsight or popularity prediction;
- a post-cutoff paper is genuine corroboration rather than a noisy proxy.

CounterGap turns this into an explicit **agent environment + temporal evaluation protocol**.

The core idea is:

1. Freeze literature at a cutoff time `T`.
2. Allow the agent to observe only pre-`T` evidence.
3. Let it search, extract claims, propose a gap, seek counter-evidence, revise or reject the gap.
4. Evaluate the final claim against:
   - pre-`T` evidence coverage;
   - counter-evidence robustness;
   - leakage checks;
   - simple baselines;
   - post-`T` emergence signals as **one imperfect validation signal**, not ground truth.
5. Log every action so that a reviewer can audit why the agent reached its conclusion.

---

## 2. Competition alignment

The attached GOAI AI for Research rules emphasize that an open-exploration project should define:

- a **real research problem**;
- an **exploration environment**;
- a **discovery signal defined before exploration**;
- a **minimal reference system / baseline**;
- a system that is **checkable and extendable**.

The rules also explicitly warn against projects that are only a large title, an LLM workflow, a screenshot, or a success criterion defined after the fact.

CounterGap is designed around those constraints rather than around a UI demo.

> Important: this repository is a development scaffold. It is not a ready-to-submit competition essay.

---

## 3. Research question

### Primary question

**Under a temporally frozen literature environment, does active counter-evidence search reduce false research-gap claims relative to one-shot gap generation and simple non-agent baselines?**

### Secondary questions

- Which search actions most often cause a gap hypothesis to be revised or rejected?
- Does the agent discover useful negative signals, such as recurring failure modes?
- How sensitive are results to the cutoff year, literature coverage, and domain?
- Can the environment distinguish a genuinely interactive agent from a one-shot LLM pipeline?
- Does post-cutoff literature add validation value beyond pre-cutoff novelty checks?

---

## 4. Scope

### In scope

- literature retrieval from a frozen local corpus;
- temporal train/evaluation splits;
- structured claim/evidence extraction;
- gap hypotheses;
- counter-evidence search;
- hypothesis revision/rejection;
- baselines;
- discovery scoring;
- full action logs;
- leakage checks;
- reproducible experiments.

### Out of scope for v0

- production paper search;
- a polished web UI;
- a commercial research assistant;
- autonomous publication writing;
- claiming that later publication proves a gap was scientifically "true";
- dependence on commercial APIs;
- integration with Gap Explorer.

---

## 5. Environment definition

### Observation

At step `t`, an agent may receive:

- query history;
- retrieved pre-cutoff documents;
- extracted claims;
- current evidence graph;
- current gap hypothesis;
- known contradictions;
- remaining search/action budget.

### Action

An agent may:

- `search(query)`
- `read(document_id)`
- `extract_claim(document_id)`
- `propose_gap(text, evidence_ids)`
- `search_counterevidence(query)`
- `revise_gap(text, evidence_ids)`
- `reject_gap(reason)`
- `stop(reason)`

### State

The environment stores:

- frozen corpus version;
- cutoff date;
- action budget;
- visible evidence;
- hidden post-cutoff corpus;
- hypothesis history;
- evidence graph;
- run metadata and random seed.

### Feedback

During exploration, feedback should avoid leaking hidden post-cutoff information.

Permitted online feedback can include:

- retrieval coverage;
- contradiction count;
- evidence-source diversity;
- query redundancy;
- remaining budget;
- rule/format validation.

Post-cutoff signals are used only in offline evaluation.

---

## 6. Discovery signals

No single metric is treated as "scientific truth".

The initial evaluation vector is:

```text
pre_cutoff_novelty
evidence_quality
counterevidence_robustness
future_emergence
reproducibility
```

A scalar score may be derived for ranking experiments, but the vector should always be reported.

### Positive discovery

A gap is well-supported by pre-cutoff evidence, survives active counter-search, and later receives independent research attention.

### Counterexample discovery

The agent proposes a gap, then finds pre-cutoff evidence showing that the gap was already studied and correctly retracts it.

### Negative discovery

A strategy fails consistently across cutoffs/domains and the failure is reproducible.

### Problem revision

The agent discovers that the initial question is too broad or ill-posed and narrows it in a traceable way.

---

## 7. Baselines

CounterGap should never be evaluated against "nothing".

Minimum baselines:

1. **Random** — random document/query selection.
2. **Keyword/Trend** — simple frequency or trend heuristic.
3. **Embedding Boundary** — semantic outlier / sparse-neighborhood heuristic.
4. **One-shot LLM** — one-pass gap generation without iterative actions.
5. **Agent without Counter-Search** — critical ablation.
6. **CounterGap Agent** — full iterative agent.

The key scientific comparison is expected to be:

```text
one-shot / no-counter-search
            vs
counter-evidence-search agent
```

---

## 8. Repository layout

```text
countergap/
├─ README.md
├─ AGENTS.md
├─ prompt.md
├─ pyproject.toml
├─ .gitignore
├─ .env.example
├─ configs/
│  ├─ base.yaml
│  └─ domains/
│     └─ demo.yaml
├─ data/
│  └─ README.md
├─ docs/
│  ├─ architecture.md
│  ├─ competition_alignment.md
│  ├─ experiment_plan.md
│  └─ leakage_checklist.md
├─ scripts/
│  ├─ build_demo_corpus.py
│  ├─ run_demo.py
│  ├─ run_llm_demo.py        # optional DeepSeek methods
│  ├─ score_trace.py         # deterministic offline scoring proxy
│  └─ evaluate.py
├─ src/
│  └─ countergap/
│     ├─ __init__.py
│     ├─ config.py           # tiny .env loader (stdlib only)
│     ├─ schemas.py
│     ├─ env.py
│     ├─ scoring.py
│     ├─ adapters/
│     │  ├─ literature.py
│     │  └─ llm.py           # LLMClient protocol + DeepSeekClient
│     ├─ agents/
│     │  ├─ counter_search.py
│     │  ├─ llm_counter_search.py  # M2: LLM-driven falsification agent
│     │  ├─ no_counter_search.py
│     │  └─ prompts.py
│     ├─ baselines/
│     │  ├─ random_agent.py
│     │  ├─ keyword_trend.py
│     │  ├─ keyword_trend_agent.py
│     │  ├─ one_shot.py
│     │  └─ one_shot_llm.py  # M1: one-shot LLM baseline
│     └─ evaluation/
│        ├─ temporal_split.py
│        └─ runner.py
├─ tests/
│  ├─ test_temporal_split.py
│  ├─ test_scoring.py
│  ├─ test_llm_adapter.py
│  └─ test_llm_agents.py
└─ outputs/
   └─ .gitkeep
```

---

## 9. Quick start

Python 3.11+ is recommended.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Build the local toy corpus:

```bash
python scripts/build_demo_corpus.py
```

Run the deterministic demo:

```bash
python scripts/run_demo.py
```

These commands work directly from the repository folder; installing the
package is optional for the demo workflow.

It writes one trace per method: Random, One-shot, No-counter-search, and the
Counter-search agent. All four use the same toy corpus, cutoff, seed, and
action budget; their score records remain pending manual offline evaluation.

Run tests:

```bash
pytest
```

Offline scoring is deliberately separate from the agent run. After manually
reviewing a completed trace, supply a JSON file matching `OfflineEvaluation`
(`run_id`, `evaluator_id`, rubric version, evidence categories, terminal
assessment, verdict, and score components). `future_emergence` may be `null`
only with an explicit `not_evaluated` or `not_applicable` status:

```bash
python scripts/evaluate.py --trace outputs/demo_counter_search_trace.jsonl --assessment reviewed_assessment.json
```

This writes a linked `offline_evaluation` JSONL record without altering the
original trace. Future-document IDs, if used as corroboration, belong only in
this post-run assessment.

Terminal runs distinguish a validated candidate from `NO_VALIDATED_GAP`,
`INSUFFICIENT_EVIDENCE`, and other non-claim outcomes. An active hypothesis
cannot terminate until it has been targeted by both a support search and a
counter-evidence search; every revision resets that requirement.

For a no-install local review form, double-click `reviewer.html`, choose a
trace from `outputs/`, complete the form, and export the resulting assessment
JSON. You can attach that JSON in a later chat message or pass it to
`scripts/evaluate.py`.

The v0 demo uses no API and is deliberately small. Its purpose is to validate environment semantics, temporal isolation, logging, and scoring before adding real literature retrieval or an LLM.

### Optional: DeepSeek LLM methods

The base repository requires **no API key** (AGENTS.md §9). If you want to run
the two LLM-backed methods — `one_shot_llm` (M1 one-shot baseline) and
`llm_counter_search` (M2 interactive falsification agent) — provide a key:

```powershell
Copy-Item .env.example .env   # then edit .env and set DEEPSEEK_API_KEY
python scripts/run_llm_demo.py
```

The key lives only in the gitignored `.env` file; it never enters traces or
commits. See `docs/llm_integration.md` for the interface, the no-leak
guarantees, and why LLM runs are non-deterministic.

Score any completed trace with the deterministic offline proxy (provisional
automated rubric — not a human review):

```bash
python scripts/score_trace.py --trace outputs/demo_llm_counter_search_trace.jsonl
```

Reproducibility and the AGENTS.md §8 manual-inspection sample:

```bash
python scripts/run_grid.py            # 5 seeds × 6 deterministic methods → 30 traces
python scripts/run_grid.py --llm      # + DeepSeek methods (first 2 seeds)
python scripts/inspect_trace.py outputs/grid_counter_search_seed42_trace.jsonl
```

The grid verifies that deterministic methods produce semantically identical
traces across seeds (see `docs/trace_inspection.md` for the findings).

---

## 10. Development milestones

### M0 — Environment correctness — DONE (verified)

- [x] schemas, temporal split, local corpus adapter, action log, leakage tests
- [x] deterministic toy run: `pytest` green (34 tests), `run_demo.py` writes 4 traces

### M1 — Baselines — DONE (toy corpus)

- [x] random; keyword/trend (runnable); one-shot heuristic
- [x] embedding boundary (bag-of-words cosine proxy, no new deps; real embeddings deferred to M3)
- [x] one-shot LLM baseline (`one_shot_llm.py`, optional DeepSeek)

### M2 — Counter-search agent — PARTIAL

- [x] deterministic heuristic agent (`counter_search.py`)
- [x] LLM-driven agent (`llm_counter_search.py`, optional DeepSeek)
- [x] multi-seed grid script (`run_grid.py`); LLM stable 2/2 seeds on toy corpus
- [ ] multi-domain grid once a real corpus exists

### M3 — Real corpus — DEFERRED

A real domain corpus requires stable bibliographic metadata, publication
dates, legally available abstracts, and versioned snapshots. The licensing and
scope decision is a deliberate stop point (AGENTS.md §13): the toy corpus
remains the only license-safe option until a corpus is chosen.

### M4 — Competition evidence pack — PARTIAL

- [x] architecture figure (`docs/architecture.md`), baseline table (see below)
- [x] example exploration traces (`outputs/*.jsonl`, regenerated by running the demos)
- [x] leakage audit (`docs/leakage_checklist.md`), reproducibility commands
- [x] 34-trace manual inspection (`docs/trace_inspection.md`, AGENTS.md §8) — toy-corpus only; redo on the real corpus before any claim

### Demo results (toy corpus, cutoff 2022-12-31, seed 42, budget 16)

Provisional automated rubric (`countergap_auto_v1`, not human review; one
representative run per method, LLM values vary between seeds):

| method | terminal outcome | steps | novelty | evidence | robust | future | repro | agg |
|---|---|---|---|---|---|---|---|---|
| random | insufficient_evidence | 5 | 0.93 | 0.07 | 0.30 | 0.00 | 1.0 | 0.425 |
| keyword_trend | insufficient_evidence | 10 | 0.97 | 0.02 | 0.30 | 0.03 | 1.0 | 0.426 |
| one_shot | insufficient_evidence | 6 | 0.95 | 0.04 | 0.30 | 0.09 | 1.0 | 0.438 |
| no_counter_search | insufficient_evidence | 8 | 0.95 | 0.00 | 0.30 | 0.06 | 1.0 | 0.420 |
| counter_search | insufficient_evidence | 10 | 1.00 | 0.00 | 0.30 | 0.08 | 1.0 | 0.438 |
| embedding_boundary | insufficient_evidence | 12 | 0.97 | 0.00 | 0.30 | 0.03 | 1.0 | 0.430 |
| one_shot_llm (DeepSeek) | insufficient_evidence | 6 | 0.79 | 0.16 | 0.30 | 0.11 | 0.5 | 0.381 |
| llm_counter_search (DeepSeek) | **validated_candidate_gap** | 10 | 0.83 | 0.15 | 0.80 | 0.12 | 0.5 | 0.513 |

Only the interactive LLM agent produced a terminal `validated_candidate_gap`
(2/2 seeds, see `docs/trace_inspection.md`): it proposed a specific claim,
generated falsification queries, searched the frozen corpus for pre-cutoff
counter-evidence, judged the claim to survive, and challenged the final
hypothesis with both a support and a counter search before stopping. The
one-shot LLM produced the same style of claim but could not validate it —
exactly the contrast the environment is designed to expose. Interpretation
caveats: LLM runs are non-deterministic (single seeds shown; 2-seed stability
is indicative only); the auto rubric rewards vague claims with high
"novelty" (see `score_trace.py` notes); future-emergence is automated term
overlap only; retrieval failures are indistinguishable from "no
counter-evidence" (F6 in the inspection report).

---

## 11. Gap Explorer integration

CounterGap must remain runnable without Gap Explorer.

Later integration should happen through an adapter boundary:

```python
class LiteratureBackend(Protocol):
    def search(self, query: str, cutoff: str, k: int = 10): ...
    def read(self, document_id: str): ...
```

Possible future adapters:

```text
LocalFrozenCorpusBackend
SciverseBackend
OpenAlexBackend
GapExplorerBackend
```

This keeps the scientific evaluation protocol independent of whichever product/retrieval system is available.

---

## 12. Non-negotiable scientific constraints

1. **No temporal leakage.**
   Post-cutoff documents must never influence agent actions.

2. **Future publication is not ground truth.**
   It is only one offline signal.

3. **No hidden normalization leakage.**
   Statistics, embeddings, index construction, and feature fitting must be audited for use of post-cutoff data.

4. **Every gap claim requires evidence.**
   Unsupported text is not a discovery.

5. **Every baseline receives the same information budget whenever possible.**

6. **Report failures.**
   Retractions, contradictions, dead ends, and invalid hypotheses are part of the result.

7. **Avoid benchmark overfitting.**
   A method that works only for one cutoff/domain is not yet a general research-discovery method.

8. **Do not confuse retrieval coverage with truth.**
   A missing paper may be an index failure rather than a real gap.

---

## 13. What would falsify the project hypothesis?

CounterGap is scientifically useful only if it can lose.

Examples:

- counter-search does not reduce false-gap rate;
- a keyword/trend baseline matches the agent;
- results collapse when cutoff dates change;
- future-emergence signal is nearly uncorrelated with human judgments;
- the agent mostly learns corpus artifacts;
- the majority of "gaps" disappear when corpus coverage improves.

Any of these is a legitimate research outcome.

---

## 14. Immediate next task

Do **not** build a frontend.

First:

1. run the toy environment;
2. verify temporal isolation;
3. choose one real domain;
4. create a frozen corpus snapshot;
5. run Random vs One-shot vs No-counter-search vs Counter-search;
6. inspect at least 20 traces manually;
7. only then consider LLM/model integrations.

See `prompt.md` for the coding-agent execution prompt and `AGENTS.md` for repository operating rules.
