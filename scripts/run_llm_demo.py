"""Run the full method suite including optional DeepSeek LLM methods.

Compares, on the same frozen toy corpus/cutoff/seed/budget:

    random, keyword_trend, one_shot, no_counter_search, counter_search,
    embedding_boundary, one_shot_llm, llm_counter_search

LLM methods require ``DEEPSEEK_API_KEY`` (from a gitignored ``.env`` file).
Use ``--skip-llm`` to run only the deterministic methods.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.adapters.llm import DeepSeekClient, LLMError
from countergap.agents.counter_search import CounterSearchAgent
from countergap.agents.llm_counter_search import LLMCounterSearchAgent
from countergap.agents.no_counter_search import NoCounterSearchAblation
from countergap.baselines.embedding_boundary import EmbeddingBoundaryBaseline
from countergap.baselines.keyword_trend_agent import KeywordTrendBaseline
from countergap.baselines.one_shot import OneShotBaseline
from countergap.baselines.one_shot_llm import OneShotLLMBaseline
from countergap.baselines.random_agent import RandomBaseline
from countergap.config import load_dotenv
from countergap.env import CounterGapEnv
from countergap.evaluation.runner import write_run_trace
from countergap.evaluation.temporal_split import temporal_split
from countergap.schemas import Document, RunMetadata, TerminalOutcome


def load_docs(path: Path) -> list[Document]:
    docs = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                docs.append(Document.model_validate_json(line))
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cutoff", default="2022-12-31")
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()

    cutoff = date.fromisoformat(args.cutoff)
    corpus = ROOT / "data" / "demo_corpus.jsonl"
    if not corpus.exists():
        raise SystemExit("Run: python scripts/build_demo_corpus.py")
    docs = load_docs(corpus)
    pre, post = temporal_split(docs, cutoff)

    llm = None
    if not args.skip_llm:
        load_dotenv()
        try:
            llm = DeepSeekClient()
        except LLMError as error:
            raise SystemExit(f"--skip-llm not set but {error}")

    methods: dict[str, object] = {
        "random": RandomBaseline(seed=args.seed),
        "keyword_trend": KeywordTrendBaseline(),
        "one_shot": OneShotBaseline(),
        "no_counter_search": NoCounterSearchAblation(),
        "counter_search": CounterSearchAgent(),
        "embedding_boundary": EmbeddingBoundaryBaseline(),
    }
    if llm is not None:
        methods["one_shot_llm"] = OneShotLLMBaseline(llm=llm)
        methods["llm_counter_search"] = LLMCounterSearchAgent(llm=llm)

    runs: dict[str, object] = {}
    for method_name, method in methods.items():
        backend = LocalFrozenCorpusBackend(docs, cutoff=cutoff)
        env = CounterGapEnv(backend=backend, cutoff=cutoff, action_budget=args.budget)
        method.run(env)
        run_id = f"demo-{method_name}-seed-{args.seed}-cutoff-{cutoff.isoformat()}"
        out = write_run_trace(
            env,
            RunMetadata(
                run_id=run_id,
                seed=args.seed,
                corpus_version="demo-v1",
                cutoff=cutoff,
                method_name=method_name,
                action_budget=args.budget,
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
        "budget": args.budget,
        "seed": args.seed,
        "llm_enabled": llm is not None,
        "runs": runs,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
