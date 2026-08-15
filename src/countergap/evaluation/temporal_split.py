from __future__ import annotations

from datetime import date

from countergap.schemas import Document


def temporal_split(
    documents: list[Document],
    cutoff: date,
) -> tuple[list[Document], list[Document]]:
    """Split documents deterministically.

    Semantics:
    - publication_date <= cutoff: visible pre-cutoff corpus
    - publication_date > cutoff: hidden post-cutoff corpus
    """
    pre = [d for d in documents if d.publication_date <= cutoff]
    post = [d for d in documents if d.publication_date > cutoff]

    pre.sort(key=lambda d: (d.publication_date, d.document_id))
    post.sort(key=lambda d: (d.publication_date, d.document_id))
    return pre, post
