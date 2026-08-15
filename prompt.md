# CounterGap — Master Coding Prompt

You are implementing **CounterGap**, a research environment for evaluating Research Gap Discovery agents under temporal literature freezing.

Read `README.md` and `AGENTS.md` before changing code.

## Primary research question

> Under a temporally frozen literature environment, does active counter-evidence search reduce false research-gap claims relative to one-shot generation and simple baselines?

Do not turn this repository into a generic AI scientist or web product.

---

## Current objective

Complete **M0: Environment Correctness** first.

The result must be runnable locally without any API key.

### M0 deliverables

1. A toy literature corpus with:
   - document id;
   - title;
   - abstract;
   - publication date;
   - topic/domain;
   - optional manually encoded claim tags for toy evaluation only.

2. A deterministic temporal split:
   - pre-cutoff corpus;
   - hidden post-cutoff corpus;
   - explicit cutoff semantics;
   - unit tests preventing leakage.

3. A literature backend protocol and local implementation:
   - `search(query, cutoff, k)`
   - `read(document_id)`

4. An environment with:
   - observation;
   - actions;
   - state;
   - finite budget;
   - append-only action log.

5. Initial action types:
   - search;
   - read;
   - propose gap;
   - search counter-evidence;
   - revise gap;
   - reject gap;
   - stop.

6. A deterministic heuristic `CounterSearchAgent` for the toy corpus.
   - It does not need an LLM.
   - Its purpose is to prove the environment loop.

7. At least:
   - random baseline;
   - one-shot heuristic baseline.

8. A score vector:
   - pre-cutoff novelty;
   - evidence quality;
   - counter-evidence robustness;
   - future emergence;
   - reproducibility.

9. JSONL output for each run.

10. Tests:
    - temporal leakage;
    - deterministic seed;
    - budget enforcement;
    - scoring bounds.

---

## Required implementation order

Do not jump ahead.

### Task 1 — Schemas
Implement/verify data models in:

```text
src/countergap/schemas.py
```

### Task 2 — Temporal split
Implement:

```text
src/countergap/evaluation/temporal_split.py
tests/test_temporal_split.py
```

Stop and run tests.

### Task 3 — Local literature backend
Implement:

```text
src/countergap/adapters/literature.py
scripts/build_demo_corpus.py
```

Stop and run a simple retrieval smoke test.

### Task 4 — Environment
Implement:

```text
src/countergap/env.py
```

Verify:
- action budget;
- valid/invalid actions;
- append-only trace;
- hidden future corpus is inaccessible to agent methods.

### Task 5 — Scoring
Implement:

```text
src/countergap/scoring.py
tests/test_scoring.py
```

Do not treat post-cutoff emergence as ground truth.

### Task 6 — Baselines
Implement:

```text
src/countergap/baselines/random_agent.py
src/countergap/baselines/one_shot.py
src/countergap/baselines/keyword_trend.py
```

Keep them simple and interpretable.

### Task 7 — Counter-search agent
Implement:

```text
src/countergap/agents/counter_search.py
```

Required behavioral difference:

```text
propose -> explicitly seek counter-evidence -> revise/reject/retain
```

### Task 8 — Runner
Implement:

```text
src/countergap/evaluation/runner.py
scripts/run_demo.py
scripts/evaluate.py
```

Save a JSONL trace to `outputs/`.

### Task 9 — Verification
Run:

```bash
pytest
python scripts/build_demo_corpus.py
python scripts/run_demo.py
python scripts/evaluate.py
```

Report exact results and remaining limitations.

---

## Research invariants

Never violate these.

1. Post-cutoff documents cannot affect agent actions.
2. No feature/index/statistic may be fit on future documents unless used only in offline evaluation.
3. Future publication is an imperfect corroboration signal, not truth.
4. Baselines must receive comparable information/action budgets.
5. Every final gap must reference observable evidence.
6. Retraction is a valid successful behavior.
7. A simple baseline outperforming the agent is a valid result.
8. No fabricated papers, results, or citations.

---

## Do not do yet

Do not:

- build frontend;
- deploy;
- add authentication;
- add vector database;
- integrate Gap Explorer;
- add Sciverse/OpenAlex APIs;
- add paid model APIs;
- add multi-agent orchestration framework;
- optimize performance;
- write competition submission prose.

Those are future tasks.

---

## Work style

For each task:

```text
Goal:
Files touched:
Invariant:
Implementation:
Verification:
Remaining risk:
Next task:
```

If you get stuck, inspect the concrete failure before changing architecture.

Do not repeatedly oscillate between similar fixes without new evidence.

If subagents are available, assign one bounded task per subagent and reconcile results centrally.

---

## Final M0 report format

When M0 is finished, return:

```text
1. What runs
2. Commands
3. Tests passed/failed
4. Example trace path
5. Example score vector
6. Leakage protections
7. Known scientific limitations
8. Next recommended experiment
```

Do not claim M1/M2/M3 are complete unless they are actually implemented and verified.
