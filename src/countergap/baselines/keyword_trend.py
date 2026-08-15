from __future__ import annotations

from collections import Counter

from countergap.schemas import Document


def rare_tag_candidates(documents: list[Document], n: int = 5) -> list[str]:
    """Very simple baseline: return the rarest explicit toy-corpus tags."""
    counts = Counter(tag for d in documents for tag in d.tags)
    return [tag for tag, _ in sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))[:n]]
