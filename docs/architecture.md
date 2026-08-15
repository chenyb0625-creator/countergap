# Architecture

```text
                         ┌──────────────────────┐
                         │ Experiment Config    │
                         │ cutoff / seed / budget│
                         └──────────┬───────────┘
                                    │
                  ┌─────────────────▼─────────────────┐
                  │ TemporalSplit                    │
                  │ visible_pre_T | hidden_post_T    │
                  └──────────┬───────────────┬───────┘
                             │               │
                   agent path│               │offline evaluation only
                             │               │
                 ┌───────────▼──────┐   ┌────▼─────────────┐
                 │ LiteratureBackend │   │ Future Evaluator │
                 └───────────┬──────┘   └──────────────────┘
                             │
                      ┌──────▼──────┐
                      │ CounterGapEnv│
                      │ state/actions│
                      └──────┬──────┘
                             │
               ┌─────────────▼─────────────┐
               │ Agent or Baseline         │
               │ random / one-shot / full  │
               └─────────────┬─────────────┘
                             │
                      ┌──────▼──────┐
                      │ JSONL Trace  │
                      └──────┬──────┘
                             │
                      ┌──────▼──────┐
                      │ Score Vector │
                      └─────────────┘
```

## Boundary principle

The environment owns the cutoff and visible-document set.

The agent never receives the hidden post-cutoff corpus object.

This is a stronger design than relying on the agent to "remember not to use future papers".
