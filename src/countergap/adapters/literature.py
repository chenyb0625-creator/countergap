from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Protocol

from countergap.schemas import Document


class LiteratureBackend(Protocol):
    cutoff: date

    def search(self, query: str, k: int = 10) -> list[Document]: ...
    def read(self, document_id: str) -> Document: ...


class LocalFrozenCorpusBackend:
    """Agent-facing backend that materializes only pre-cutoff documents."""

    def __init__(self, documents: list[Document], cutoff: date):
        self.cutoff = cutoff
        self._docs = {
            document.document_id: document
            for document in documents
            if document.publication_date <= cutoff
        }

    @classmethod
    def from_jsonl(
        cls,
        path: str | Path,
        cutoff: date,
    ) -> "LocalFrozenCorpusBackend":
        docs: list[Document] = []
        with Path(path).open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    docs.append(Document.model_validate_json(line))
        return cls(docs, cutoff)

    def search(self, query: str, k: int = 10) -> list[Document]:
        terms = {t.lower() for t in query.split() if t.strip()}
        scored: list[tuple[int, str, Document]] = []
        for d in self._docs.values():
            hay = f"{d.title} {d.abstract} {' '.join(d.tags)}".lower()
            score = sum(hay.count(t) for t in terms)
            scored.append((score, d.document_id, d))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [d for score, _, d in scored if score > 0][:k]

    def read(self, document_id: str) -> Document:
        if document_id not in self._docs:
            raise KeyError(f"Unknown or inaccessible document_id: {document_id}")
        return self._docs[document_id]
