from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from countergap.schemas import Document


DOCS = [
    Document(
        document_id="d1",
        title="Automated literature mapping for scientific review",
        abstract="A pipeline retrieves and clusters literature to support human review.",
        publication_date="2020-03-01",
        domain="ai_research",
        tags=["literature", "retrieval", "review"],
    ),
    Document(
        document_id="d2",
        title="Language models for research question generation",
        abstract="A language model generates candidate research questions from scientific abstracts.",
        publication_date="2021-06-15",
        domain="ai_research",
        tags=["llm", "question_generation", "research_gap"],
    ),
    Document(
        document_id="d3",
        title="Evidence-grounded scientific hypothesis generation",
        abstract="Generated hypotheses are linked to supporting documents and checked for textual entailment.",
        publication_date="2022-08-10",
        domain="ai_research",
        tags=["hypothesis", "evidence", "grounding"],
    ),
    Document(
        document_id="d4",
        title="Falsification loops for machine-generated scientific hypotheses",
        abstract="Candidate hypotheses are challenged with adversarial evidence retrieval before acceptance.",
        publication_date="2022-11-20",
        domain="ai_research",
        tags=["hypothesis", "falsification", "counter_evidence"],
    ),
    Document(
        document_id="d5",
        title="Temporal evaluation of autonomous research agents",
        abstract="Research agents are evaluated on literature snapshots that hide future publications.",
        publication_date="2023-05-12",
        domain="ai_research",
        tags=["agent", "temporal", "evaluation"],
    ),
    Document(
        document_id="d6",
        title="Benchmarking research gap discovery with future literature",
        abstract="Later literature is used as one weak corroboration signal for historical gap predictions.",
        publication_date="2024-02-01",
        domain="ai_research",
        tags=["research_gap", "benchmark", "future_emergence"],
    ),
]

out = ROOT / "data" / "demo_corpus.jsonl"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", encoding="utf-8") as f:
    for doc in DOCS:
        f.write(doc.model_dump_json() + "\n")

print(f"Wrote {len(DOCS)} synthetic documents to {out}")
