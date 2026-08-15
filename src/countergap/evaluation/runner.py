from __future__ import annotations

import json
from pathlib import Path

from countergap.env import CounterGapEnv
from countergap.schemas import (
    OfflineEvaluation,
    RunMetadata,
    RunSummary,
    TerminalOutcome,
)
from countergap.scoring import aggregate_score


def write_run_trace(
    env: CounterGapEnv,
    metadata: RunMetadata,
    path: str | Path,
    summary: RunSummary | None = None,
) -> Path:
    """Write one auditable run as JSONL after the environment has stopped.

    Scores are optional until a separate offline evaluator has completed. This
    prevents post-cutoff evidence from entering the agent-facing execution path.
    """
    if metadata.cutoff != env.cutoff:
        raise ValueError("Run metadata cutoff must match the environment cutoff.")
    if metadata.action_budget != env.action_budget:
        raise ValueError("Run metadata action budget must match the environment budget.")
    if not env.stopped:
        raise ValueError("Only completed runs can be written to an audit trace.")

    if summary is None:
        stop_reason = "stopped"
        if env.trace:
            stop_reason = str(env.trace[-1].action.payload.get("reason", stop_reason))
        summary = RunSummary(
            stop_reason=stop_reason,
            terminal_outcome=env.terminal_outcome,
            final_hypothesis=(
                env.hypothesis
                if env.terminal_outcome == TerminalOutcome.VALIDATED_CANDIDATE_GAP
                else None
            ),
            last_hypothesis=env.hypothesis,
            hypothesis_history=env.hypothesis_history,
            revision_history=env.revision_history,
            evidence_state=env.evidence_state(),
            stop_decision=env.stop_decision,
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({
            "record_type": "run_start",
            "run_id": metadata.run_id,
            "metadata": metadata.model_dump(mode="json"),
        }) + "\n")
        for event in env.trace:
            f.write(json.dumps({
                "record_type": "action",
                "run_id": metadata.run_id,
                "event": event.model_dump(mode="json"),
            }) + "\n")
        f.write(json.dumps({
            "record_type": "run_end",
            "run_id": metadata.run_id,
            "summary": summary.model_dump(mode="json"),
        }) + "\n")
    return path


def write_offline_evaluation(
    trace_path: str | Path,
    evaluation: OfflineEvaluation,
    output_path: str | Path,
) -> Path:
    """Write a reviewer-provided offline score without modifying the run trace."""
    trace_path = Path(trace_path)
    with trace_path.open("r", encoding="utf-8") as f:
        first_record = json.loads(f.readline())
    if first_record.get("record_type") != "run_start":
        raise ValueError("Trace must begin with a run_start record.")
    if first_record.get("run_id") != evaluation.run_id:
        raise ValueError("Offline evaluation run_id must match the trace run_id.")

    record = {
        "record_type": "offline_evaluation",
        "run_id": evaluation.run_id,
        "evaluation": evaluation.model_dump(mode="json"),
        "aggregate_score": aggregate_score(evaluation.score_vector),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return output_path
