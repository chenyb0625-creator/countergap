# Competition Alignment Notes

This project is designed for the **open exploration** framing rather than as a conventional leaderboard-only algorithm entry.

The competition material emphasizes:

- real unresolved / insufficiently structured research problems;
- a clearly defined environment;
- fixed vs explorable variables;
- feedback mechanisms;
- discovery signals defined in advance;
- minimal baselines/reference systems;
- checkable action logs and reproducibility;
- value in negative results and problem revision.

CounterGap maps these directly:

| Competition concept | CounterGap implementation |
|---|---|
| Real problem | reliability/evaluation of Research Gap Discovery |
| Exploration environment | temporally frozen literature corpus |
| Fixed part | corpus snapshot, cutoff, budget, evaluation protocol |
| Explorable part | queries, documents, hypotheses, evidence graph |
| Feedback | coverage, contradiction, budget, evidence quality |
| Discovery signal | novelty + evidence + robustness + future emergence |
| Minimal reference | random / keyword / one-shot / no-counter-search |
| Checkability | JSONL action trace |
| Extendability | adapter-based corpus and agent interfaces |

The project should be judged by whether the research environment is scientifically coherent, not by the number of product features.
