"""Human-inspection helper: print a compact, faithful summary of one trace.

AGENTS.md §8 requires *manual* trace inspection — this script only organizes
what happened (actions, queries, reads, hypothesis evolution, stop decision)
so a reviewer can read the actual behaviour. It performs no judgment and no
scoring. Run it over any number of traces; a summary block is printed per
trace, with enough detail to audit whether the claimed gap was really
searched, whether counter-evidence was absorbed, and why the run stopped.

Usage:
    python scripts/inspect_trace.py outputs/grid_counter_search_seed42_trace.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def summarize(path: Path) -> None:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    metadata = records[0]["metadata"]
    summary = records[-1]["summary"]
    print("=" * 78)
    print(f"TRACE: {path.name}")
    print(f"  method={metadata['method_name']} seed={metadata['seed']} "
          f"budget={metadata['action_budget']} run_id={metadata['run_id']}")
    print(f"  terminal_outcome={summary['terminal_outcome']}")
    print(f"  stop_reason={summary['stop_reason']}")

    for record in records:
        if record.get("record_type") != "action":
            continue
        event = record["event"]
        action = event["action"]
        payload = action["payload"]
        step = event["step"]
        exposed = event["exposed_document_ids"]
        line = f"  [{step:>2}] {action['type']:<22}"
        if action["type"] in ("search", "search_counterevidence"):
            line += f"q={payload.get('query')!r}"
            if exposed:
                line += f" -> exposed {exposed}"
        elif action["type"] == "read":
            line += f"doc={payload.get('document_id')}"
        elif action["type"] in ("propose_gap", "revise_gap", "reject_gap", "abandon_gap", "stop"):
            line += (payload.get("text") or payload.get("reason") or "")[:130]
        print(line)

    hypothesis = summary.get("final_hypothesis") or summary.get("last_hypothesis")
    if hypothesis:
        print(f"  FINAL HYPOTHESIS [{hypothesis['hypothesis_id']} status={hypothesis['status']}]")
        print(f"    text: {hypothesis['text'][:220]}")
        print(f"    evidence={hypothesis['evidence_ids']} "
              f"counterevidence={hypothesis['counterevidence_ids']} "
              f"final_claim_evidence={hypothesis['final_claim_evidence_ids']}")
        print(f"    targeted_search={hypothesis['targeted_search_count']} "
              f"counter_search={hypothesis['counter_search_count']} "
              f"terminal_eligible={hypothesis['terminal_eligible']}")
    evidence_state = summary.get("evidence_state") or {}
    print(f"  evidence_state: read={evidence_state.get('read_document_ids')} "
          f"retrieved={len(evidence_state.get('retrieved_document_ids', []))}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", nargs="+", type=Path)
    args = parser.parse_args()
    for trace in args.traces:
        summarize(trace)


if __name__ == "__main__":
    main()
