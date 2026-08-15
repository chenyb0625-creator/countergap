"""Run a multi-seed grid to sample 20+ traces for manual inspection.

AGENTS.md §8 requires sampling at least 20 traces before any claim. This
script runs every deterministic method over ``--seeds`` and, with ``--llm``,
the two DeepSeek methods over the first two seeds.

It also verifies a reproducibility invariant: deterministic methods must
produce byte-identical traces regardless of the seed passed in.

Usage:
    python scripts/run_grid.py                      # deterministic only, 5 seeds
    python scripts/run_grid.py --llm                # + LLM methods (needs .env key)
    python scripts/run_grid.py --seeds 42 7 2024 --budget 16
"""

from __future__ import annotations

import argparse
import hashlib
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
from countergap.schemas import Document, RunMetadata


def load_docs(path: Path) -> list[Document]:
    return [
        Document.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 7, 2024, 1234, 99])
    parser.add_argument("--budget", type=int, default=16)
    parser.add_argument("--cutoff", default="2022-12-31")
    parser.add_argument("--cutoffs", nargs="+", default=None, help="multiple cutoffs (overrides --cutoff)")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data" / "demo_corpus.jsonl")
    parser.add_argument("--corpus-version", default="demo-v1")
    parser.add_argument("--llm", action="store_true", help="also run the two DeepSeek methods")
    args = parser.parse_args()

    cutoffs_iso = args.cutoffs or [args.cutoff]
    corpus = args.corpus
    if not corpus.exists():
        raise SystemExit(f"Corpus not found: {corpus}")
    docs = load_docs(corpus)

    deterministic_factories = {
        "random": RandomBaseline,
        "keyword_trend": KeywordTrendBaseline,
        "one_shot": OneShotBaseline,
        "no_counter_search": NoCounterSearchAblation,
        "counter_search": CounterSearchAgent,
        "embedding_boundary": EmbeddingBoundaryBaseline,
    }

    traces_by_method: dict[str, list[Path]] = {name: [] for name in deterministic_factories}

    for cutoff_iso in cutoffs_iso:
        cutoff = date.fromisoformat(cutoff_iso)
        for seed in args.seeds:
            for name, factory in deterministic_factories.items():
                backend = LocalFrozenCorpusBackend(docs, cutoff=cutoff)
                env = CounterGapEnv(backend=backend, cutoff=cutoff, action_budget=args.budget)
                method = factory(seed=seed) if name == "random" else factory()
                method.run(env)
                safe_cutoff = cutoff_iso.replace("-", "")
                out = write_run_trace(
                    env,
                    RunMetadata(
                        run_id=f"grid-{name}-seed-{seed}-cutoff-{cutoff_iso}",
                        seed=seed,
                        corpus_version=args.corpus_version,
                        cutoff=cutoff,
                        method_name=name,
                        action_budget=args.budget,
                    ),
                    ROOT / "outputs" / f"grid_{args.corpus_version}_{name}_seed{seed}_c{safe_cutoff}_trace.jsonl",
                )
                traces_by_method[name].append(out)

    # Reproducibility check: deterministic methods must ignore the seed value.
    # Timestamps differ by construction, so compare the semantic trace content
    # (action type + payload + exposed ids + terminal summary) instead of bytes.
    def _semantic_hash(path: Path) -> str:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        semantic = []
        for record in records:
            if record["record_type"] == "action":
                event = record["event"]
                semantic.append({
                    "type": event["action"]["type"],
                    "payload": event["action"]["payload"],
                    "exposed": event["exposed_document_ids"],
                })
            elif record["record_type"] == "run_end":
                summary = record["summary"]
                semantic.append({
                    "terminal_outcome": summary["terminal_outcome"],
                    "last_hypothesis": summary["last_hypothesis"],
                    "stop_reason": summary["stop_reason"],
                })
        return hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()[:12]

    print("=== deterministic reproducibility (semantic hash across seeds) ===")
    for name, paths in traces_by_method.items():
        digests = {_semantic_hash(p) for p in paths}
        print(f"{name:20s} {'IDENTICAL' if len(digests) == 1 else 'DIFFERS'} ({len(paths)} traces)")

    llm_summary: dict[str, list[dict]] = {}
    if args.llm:
        load_dotenv()
        try:
            llm = DeepSeekClient()
        except LLMError as error:
            raise SystemExit(f"--llm set but {error}")
        for cutoff_iso in cutoffs_iso:
            cutoff = date.fromisoformat(cutoff_iso)
            for seed in args.seeds[:2]:
                for name, factory in (
                    ("one_shot_llm", lambda: OneShotLLMBaseline(llm=llm)),
                    ("llm_counter_search", lambda: LLMCounterSearchAgent(llm=llm)),
                ):
                    backend = LocalFrozenCorpusBackend(docs, cutoff=cutoff)
                    env = CounterGapEnv(backend=backend, cutoff=cutoff, action_budget=args.budget)
                    factory().run(env)
                    safe_cutoff = cutoff_iso.replace("-", "")
                    out = write_run_trace(
                        env,
                        RunMetadata(
                            run_id=f"grid-{name}-seed-{seed}-cutoff-{cutoff_iso}",
                            seed=seed,
                            corpus_version=args.corpus_version,
                            cutoff=cutoff,
                            method_name=name,
                            action_budget=args.budget,
                        ),
                        ROOT / "outputs" / f"grid_{args.corpus_version}_{name}_seed{seed}_c{safe_cutoff}_trace.jsonl",
                    )
                    llm_summary.setdefault(name, []).append({
                        "seed": seed,
                        "cutoff": cutoff_iso,
                        "terminal_outcome": env.terminal_outcome.value if env.terminal_outcome else None,
                        "steps": len(env.trace),
                        "trace": str(out),
                    })
        print("=== LLM multi-seed outcomes ===")
        print(json.dumps(llm_summary, ensure_ascii=False, indent=2))

    total = sum(len(paths) for paths in traces_by_method.values())
    print(f"=== total deterministic traces: {total} ===")


if __name__ == "__main__":
    main()
