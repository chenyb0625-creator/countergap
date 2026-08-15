# Minimal Experiment Plan

## Hypothesis H1

Active counter-evidence search reduces false-gap claims relative to an otherwise comparable agent without counter-search.

## Unit of evaluation

One tuple:

```text
(domain, cutoff, seed, research prompt)
```

## Initial conditions

Use one narrow domain first.

Recommended experiment grid after the toy corpus:

- 1 domain;
- 3 temporal cutoffs;
- 20–50 research prompts;
- 5 seeds for stochastic agents;
- 4–6 methods/baselines.

## Methods

- Random
- Keyword/Trend
- One-shot
- Agent without counter-search
- Counter-search agent

## Primary outcome

False-gap rate under manually audited pre-cutoff evidence.

## Secondary outcomes

- retraction precision;
- evidence-source diversity;
- query efficiency;
- contradiction recovery;
- future-emergence correlation;
- score stability across cutoffs.

## Critical ablation

Keep everything fixed except counter-search capability.

This is more informative than comparing two completely different agent stacks.

## Manual review

Before making any claim:

- inspect at least 20 traces;
- classify false positives;
- inspect whether "counter-evidence" is actually relevant;
- identify corpus/index failures;
- separate retrieval failure from reasoning failure.
