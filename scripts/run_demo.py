import json
from datetime import date
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.agents.counter_search import CounterSearchAgent
from countergap.agents.no_counter_search import NoCounterSearchAblation
from countergap.baselines.one_shot import OneShotBaseline
from countergap.baselines.random_agent import RandomBaseline
from countergap.env import CounterGapEnv
from countergap.evaluation.runner import write_run_trace
from countergap.evaluation.temporal_split import temporal_split
from countergap.schemas import Document, RunMetadata
from countergap.schemas import TerminalOutcome


def load_docs(path: Path) -> list[Document]:
    docs = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                docs.append(Document.model_validate_json(line))
    return docs


def main() -> None:
    corpus = ROOT / "data" / "demo_corpus.jsonl"
    if not corpus.exists():
        raise SystemExit("Run: python scripts/build_demo_corpus.py")

    docs = load_docs(corpus)
    pre, post = temporal_split(docs, date.fromisoformat("2022-12-31"))

    cutoff = date.fromisoformat("2022-12-31")
    seed = 42
    action_budget = 12
    methods = {
        "random": RandomBaseline(seed=seed),
        "one_shot": OneShotBaseline(),
        "no_counter_search": NoCounterSearchAblation(),
        "counter_search": CounterSearchAgent(),
    }
    runs = {}
    for method_name, method in methods.items():
        backend = LocalFrozenCorpusBackend(docs, cutoff=cutoff)
        env = CounterGapEnv(backend=backend, cutoff=cutoff, action_budget=action_budget)
        method.run(env)
        out = write_run_trace(
            env,
            RunMetadata(
                run_id=f"demo-{method_name}-seed-{seed}-cutoff-{cutoff.isoformat()}",
                seed=seed,
                corpus_version="demo-v1",
                cutoff=cutoff,
                method_name=method_name,
                action_budget=action_budget,
            ),
            ROOT / "outputs" / f"demo_{method_name}_trace.jsonl",
        )
        runs[method_name] = {
            "terminal_outcome": env.terminal_outcome.value if env.terminal_outcome else None,
            "final_hypothesis": (
                env.hypothesis.model_dump()
                if env.terminal_outcome == TerminalOutcome.VALIDATED_CANDIDATE_GAP
                and env.hypothesis
                else None
            ),
            "last_hypothesis": env.hypothesis.model_dump() if env.hypothesis else None,
            "steps": len(env.trace),
            "trace_path": str(out),
        }

    print(json.dumps({
        "pre_count": len(pre),
        "hidden_post_count": len(post),
        "runs": runs,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
