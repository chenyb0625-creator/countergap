"""Build the M3 real-corpus snapshot from OpenAlex (CC0).

Domain: "language model agents" (title search, 2019-2025), sorted by
OpenAlex relevance. Only works with an abstract are kept, giving a narrow,
license-safe, versioned snapshot:

    data/llm_agent_eval_v1.jsonl      (CounterGap Document records)
    data/llm_agent_eval_v1.meta.json  (provenance: query, fetch time, counts)

Provenance and licensing:
- Source: OpenAlex REST API (CC0 data, no API key required).
- Abstracts come from the OpenAlex abstract_inverted_index (reconstructed to
  plain text here); OpenAlex terms of use permit scholarly reuse.
- The snapshot is frozen at fetch time; reproducibility metadata is written
  to the .meta.json so the corpus version is auditable.

Usage:
    python scripts/build_real_corpus.py [--limit 400] [--cutoff 2024-06-30]
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from countergap.evaluation.temporal_split import temporal_split
from countergap.schemas import Document

API = "https://api.openalex.org/works"
MAILTO = "countergap-research@example.com"
OUTPUT = ROOT / "data" / "llm_agent_eval_v1.jsonl"
META_OUTPUT = ROOT / "data" / "llm_agent_eval_v1.meta.json"


def fetch_page(filter_query: str, page: int, per_page: int) -> dict:
    params = urllib.parse.urlencode({
        "filter": filter_query,
        "per-page": per_page,
        "page": page,
        "mailto": MAILTO,
    })
    request = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": "CounterGap/0.1 (research; mailto:%s)" % MAILTO})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def rebuild_abstract(inverted: dict[str, list[int]] | None) -> str:
    """Reconstruct plain text from OpenAlex abstract_inverted_index."""
    if not inverted:
        return ""
    positions: list[tuple[int, str]] = []
    for word, indexes in inverted.items():
        for index in indexes:
            positions.append((index, word))
    positions.sort()
    return " ".join(word for _, word in positions)


def to_document(work: dict) -> Document | None:
    abstract = rebuild_abstract(work.get("abstract_inverted_index"))
    if not abstract.strip():
        return None
    doi = work.get("doi") or ""
    raw_id = doi.replace("https://doi.org/", "") if doi else work.get("id", "").rsplit("/", 1)[-1]
    document_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_id)[:80] or f"oa_{work['id']}"
    publication_date = work.get("publication_date") or f"{work.get('publication_year', 0)}-01-01"
    try:
        pub_date = date.fromisoformat(publication_date)
    except ValueError:
        pub_date = date(work.get("publication_year", 0), 1, 1)
    return Document(
        document_id=document_id,
        title=(work.get("title") or "").strip(),
        abstract=abstract.strip(),
        publication_date=pub_date,
        domain="llm_agent_eval",
        tags=["llm_agent_eval"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=400, help="max works to fetch (relevance-sorted)")
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--cutoff", default="2024-06-30", help="display cutoff for the split stats")
    args = parser.parse_args()

    filter_query = (
        "title.search:language model agents,"
        "publication_year:2019-2025"
    )
    cutoff = date.fromisoformat(args.cutoff)

    documents: list[Document] = []
    total_seen = 0
    page = 1
    while total_seen < args.limit:
        data = fetch_page(filter_query, page, args.per_page)
        results = data.get("results", [])
        if not results:
            break
        for work in results:
            if total_seen >= args.limit:
                break
            total_seen += 1
            doc = to_document(work)
            if doc is not None:
                documents.append(doc)
        page += 1
        time.sleep(0.4)  # polite rate limit
        if page > 20:
            break

    # Deterministic ordering and dedup.
    documents.sort(key=lambda d: (d.publication_date, d.document_id))
    seen_ids: set[str] = set()
    unique: list[Document] = []
    for doc in documents:
        if doc.document_id not in seen_ids:
            seen_ids.add(doc.document_id)
            unique.append(doc)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for doc in unique:
            f.write(doc.model_dump_json() + "\n")

    meta = {
        "corpus_version": "llm_agent_eval_v1",
        "domain": "llm_agent_eval",
        "source": "OpenAlex REST API (CC0)",
        "query": filter_query,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "works_seen": total_seen,
        "documents_with_abstract": len(unique),
        "api": f"{API}",
        "license_note": "OpenAlex data is CC0; abstracts reconstructed from abstract_inverted_index for scholarly reuse.",
        "reproduce": "python scripts/build_real_corpus.py --limit %d" % args.limit,
    }
    META_OUTPUT.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    pre, post = temporal_split(unique, cutoff)
    print(json.dumps({
        "corpus_version": meta["corpus_version"],
        "documents": len(unique),
        "pre_cutoff": len(pre),
        "post_cutoff_hidden": len(post),
        "cutoff": cutoff.isoformat(),
        "date_range": [unique[0].publication_date.isoformat() if unique else None,
                       unique[-1].publication_date.isoformat() if unique else None],
        "output": str(OUTPUT),
        "meta": str(META_OUTPUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
