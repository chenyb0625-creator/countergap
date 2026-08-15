# AGENTS.md

This file defines how coding agents (Codex, Workbuddy, Claude Code, etc.) must operate in the CounterGap repository.

## 0. Mission

Build a **small, falsifiable, reproducible research environment** for evaluating Research Gap Discovery agents.

The primary scientific claim to test is:

> Active counter-evidence search can reduce false research-gap claims in a temporally frozen literature environment.

The repository is **not** a generic "AI scientist", paper-search product, SaaS app, or UI project.

---

## 1. Priority order

When trade-offs exist, use this order:

1. Scientific validity
2. No temporal leakage
3. Reproducibility
4. Correct baselines and ablations
5. Auditability
6. Minimal implementation
7. Performance
8. Convenience
9. UI

Do not reverse this order.

---

## 2. Hard constraints

### 2.1 Do not overbuild

Do not add:

- web frontend;
- authentication;
- database server;
- vector DB;
- cloud deployment;
- multi-user support;
- dashboards;
- payment;
- generic plugin marketplace;
- "AI scientist" features unrelated to the central hypothesis.

unless explicitly requested.

A CLI + local files is sufficient for v0.

### 2.2 No silent architecture changes

If you believe the architecture is wrong:

1. state the issue;
2. show evidence;
3. propose the smallest change;
4. explain the scientific effect;
5. implement only after the change is clearly justified.

Do not refactor the entire repository because a different framework is more familiar.

### 2.3 No invented scientific claims

Never fabricate:

- papers;
- citations;
- benchmark results;
- statistical significance;
- human evaluation;
- dataset sizes;
- domain expertise;
- API availability.

Use placeholders only when explicitly marked as placeholders.

### 2.4 No temporal leakage

The agent-facing path must not access post-cutoff material.

This includes indirect leakage through:

- embeddings trained/fitted on the full corpus;
- vocabulary/IDF statistics computed using future documents;
- retrieval indices containing future documents;
- features derived from citation counts accumulated after the cutoff;
- post-cutoff abstracts used during prompt construction;
- hidden test labels used for threshold tuning.

If uncertain, treat it as leakage until proven otherwise.

### 2.5 Future emergence is not truth

Do not write code or documentation that equates:

```text
published later == gap was true
```

Use future publications as an imperfect offline corroboration signal only.

---

## 3. Agent work protocol

For every non-trivial coding task:

### Step A — Inspect

Read the minimum relevant files before editing.

Do not guess the current architecture.

### Step B — State the target

Write a short internal plan:

```text
Goal:
Files to touch:
Invariant to preserve:
How to verify:
Stop condition:
```

### Step C — Implement the smallest coherent change

Prefer one logical change per task.

Do not mix unrelated refactors.

### Step D — Verify

Run relevant tests or the smallest executable check.

If a test fails:

- inspect the actual failure;
- do not repeatedly rewrite unrelated code;
- do not alternate between two near-identical fixes without new evidence.

### Step E — Report

Report:

```text
Changed:
Why:
Verified with:
Remaining risk:
Next smallest task:
```

---

## 4. Subagent policy

When subagents are available, use them for **independent, bounded tasks**, not for duplicated wandering.

Recommended split:

- Subagent A: temporal leakage audit
- Subagent B: baseline implementation
- Subagent C: scoring/unit tests
- Subagent D: literature adapter
- Subagent E: experiment trace inspection

Do not run five agents on the same vague instruction.

Each subagent must have:

- a narrow deliverable;
- explicit files or outputs;
- a stop condition;
- no authority to redesign unrelated modules.

The coordinating agent must reconcile conflicting outputs manually.

---

## 5. Scientific model

### 5.1 Environment loop

Maintain the semantic loop:

```text
observation -> action -> state transition -> feedback -> next observation
```

An "agent" that only receives a prompt and emits one report is a baseline, not the target system.

### 5.2 Action budget

Every run should have a finite budget.

Examples:

- number of searches;
- number of documents read;
- number of hypothesis revisions;
- total model tokens when models are later added.

Baselines should receive comparable budgets.

### 5.3 Required logs

Each run should record:

- run id;
- random seed;
- corpus version;
- cutoff;
- agent/baseline name;
- action sequence;
- queries;
- documents exposed;
- evidence used;
- hypothesis versions;
- retraction/revision reasons;
- stop reason;
- final score vector.

No hidden reasoning text is required. Store observable actions and explicit reasons.

---

## 6. Testing requirements

Minimum tests before adding model complexity:

### Temporal split

- pre-cutoff documents visible;
- post-cutoff documents hidden;
- cutoff edge case defined;
- deterministic split.

### Scoring

- each score component bounded;
- missing evidence handled;
- zero-division handled;
- scalar aggregation deterministic.

### Environment

- budget decreases;
- invalid action rejected;
- action log is append-only;
- post-cutoff access impossible through public agent API.

### Reproducibility

- same seed + same corpus + same config => same deterministic baseline result.

---

## 7. Baseline discipline

Never remove a baseline because it performs "too well".

Required minimal baselines:

- random;
- keyword/trend;
- embedding boundary when embeddings are introduced;
- one-shot;
- no-counter-search ablation.

If a simple baseline matches the full agent, treat that as an important result.

---

## 8. Manual inspection requirement

Automated metrics are insufficient.

For any experiment intended to support a claim:

- sample at least 20 traces when dataset size permits;
- inspect the retrieved evidence;
- inspect whether a claimed gap was actually searched;
- inspect retractions and false positives;
- record common failure modes.

Do not replace this with an automated script that only checks formatting.

---

## 9. Dependency policy

Prefer:

- Python standard library;
- `pydantic`;
- `PyYAML`;
- `pytest`;
- optionally `numpy`, `pandas`, `scikit-learn` when needed.

Avoid heavyweight orchestration frameworks until the research protocol is stable.

Do not require paid APIs for the base repository.

Model integrations must be behind an interface.

---

## 10. Coding conventions

- Python 3.11+
- type hints for public functions;
- dataclasses/Pydantic for schemas;
- small modules;
- deterministic seeds;
- JSONL for run logs;
- YAML for experiment configs;
- UTF-8;
- no hard-coded absolute paths;
- no secrets committed.

---

## 11. Commit/task granularity

Good task:

> Implement deterministic temporal split and tests.

Bad task:

> Build the whole AI scientist platform.

Good task:

> Add no-counter-search ablation using existing environment actions.

Bad task:

> Refactor architecture and add vector DB because it may help later.

---

## 12. Definition of Done for v0

v0 is complete when all are true:

- [ ] toy corpus builds locally;
- [ ] temporal split is deterministic;
- [ ] post-cutoff data cannot enter agent observation;
- [ ] at least two baselines run;
- [ ] one counter-search agent run completes;
- [ ] JSONL trace is saved;
- [ ] score vector is computed;
- [ ] tests pass;
- [ ] README command works from a fresh environment;
- [ ] one trace has been manually inspected;
- [ ] no API key is required.

Anything beyond this is optional until v0 is stable.

---

## 13. Stop conditions

Stop and ask for a decision if:

- the requested change alters the research question;
- the corpus license is unclear;
- a proposed feature risks temporal leakage;
- an API is necessary but no acceptable local alternative exists;
- the metric would encode future information into the exploration loop;
- the task expands from experiment infrastructure into product engineering.

Do not improvise around these issues.

---

## 14. Relationship to Gap Explorer

Gap Explorer is a possible future retrieval/product layer.

CounterGap is the evaluation/research layer.

Do not create a hard dependency on Gap Explorer.

Integration must use an adapter interface so either project can evolve independently.
