"""Prompt builders shared by LLM-driven methods.

Every prompt is built exclusively from pre-cutoff documents that the agent has
already observed through the environment. No post-cutoff material can reach
these strings, and no hidden labels are included.
"""

from __future__ import annotations

from countergap.schemas import Document

SYSTEM_CORE = (
    "You are a research-gap discovery agent operating inside a strictly frozen "
    "literature environment. You may only rely on the documents given to you. "
    "A 'research gap' is a claim that a combination of questions, methods, or "
    "evaluations is absent from the provided literature. Do not invent papers "
    "or citations. Reply with JSON only."
)


def document_block(documents: list[Document]) -> str:
    lines = []
    for doc in documents:
        lines.append(
            f"<doc id={doc.document_id} date={doc.publication_date.isoformat()} domain={doc.domain}>"
            f"\nTITLE: {doc.title}\nABSTRACT: {doc.abstract}\n</doc>"
        )
    return "\n".join(lines)


def propose_gap_prompt(documents: list[Document]) -> str:
    """Ask the model to propose one gap claim supported by the given documents."""
    return (
        "Below are pre-cutoff documents that have already been surfaced.\n\n"
        f"{document_block(documents)}\n\n"
        "Propose exactly one research-gap claim that is supported by these "
        "documents (i.e. the combination is absent from what you see). "
        'Reply as JSON: {"gap": "<claim text>", "evidence_ids": ["<doc id>", ...]}. '
        "Every id in evidence_ids must appear in the document list above."
    )


def falsification_queries_prompt(documents: list[Document], gap: str) -> str:
    """Ask the model to generate counter-evidence search queries for the gap."""
    return (
        "Current gap claim: "
        f"{gap}\n\n"
        "Evidence already read:\n"
        f"{document_block(documents)}\n\n"
        "You must try to FALSIFY the claim. Generate up to 3 independent search "
        "queries that could surface pre-cutoff work already covering this gap. "
        "Reply as JSON: {\"queries\": [\"...\", \"...\"]}. Queries should be "
        "concise keyword phrases, not questions."
    )


def verdict_prompt(
    gap: str,
    documents: list[Document],
    counter_documents: list[Document],
) -> str:
    """Ask the model to keep, narrow, or reject the gap after counter-search."""
    counter_block = document_block(counter_documents) if counter_documents else "(none found)"
    return (
        f"Current gap claim: {gap}\n\n"
        "Pre-cutoff supporting documents:\n"
        f"{document_block(documents)}\n\n"
        "Pre-cutoff counter-evidence found by falsification search:\n"
        f"{counter_block}\n\n"
        'Decide the fate of the claim. Reply as JSON with exactly one "decision" '
        'in {"retain", "revise", "reject"}:\n'
        '- retain: keep the claim, evidence_ids = supporting ids you rely on, '
        "final_claim_evidence_ids = ids that justify the claim today.\n"
        '- revise: narrow/change the claim; provide "revised_gap", '
        '"evidence_ids" (support), "counterevidence_ids" (the counter docs), '
        '"reason", "revision_type" in {scope_narrowing, scope_broadening, '
        "definition_change, population_change, method_change, "
        "evaluation_setting_change, temporal_constraint_added}, "
        '"changed_dimensions" (list of strings).\n'
        '- reject: give up the claim; provide "reason" and "counterevidence_ids".\n'
        "All document ids must come from the lists above."
    )
