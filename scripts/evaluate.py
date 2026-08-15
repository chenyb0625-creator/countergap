"""Persist a reviewer-supplied offline evaluation for a completed run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from countergap.evaluation.runner import write_offline_evaluation
from countergap.schemas import OfflineEvaluation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True, help="Completed run JSONL trace")
    parser.add_argument(
        "--assessment",
        type=Path,
        required=True,
        help="Reviewer JSON matching the OfflineEvaluation schema",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Offline evaluation JSONL output (default: beside the trace)",
    )
    args = parser.parse_args()

    evaluation = OfflineEvaluation.model_validate_json(
        args.assessment.read_text(encoding="utf-8")
    )
    output = args.output or args.trace.with_name(f"{args.trace.stem}.evaluation.jsonl")
    written = write_offline_evaluation(args.trace, evaluation, output)
    print(json.dumps({"evaluation_path": str(written), "run_id": evaluation.run_id}))


if __name__ == "__main__":
    main()
