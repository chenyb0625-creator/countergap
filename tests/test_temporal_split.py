from datetime import date

import pytest

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.env import CounterGapEnv
from countergap.evaluation.temporal_split import temporal_split
from countergap.schemas import Action, ActionType, Document


def make_doc(doc_id: str, d: str) -> Document:
    return Document(
        document_id=doc_id,
        title=doc_id,
        abstract="",
        publication_date=d,
        domain="test",
    )


def test_cutoff_is_inclusive_for_pre_corpus():
    docs = [
        make_doc("before", "2022-12-30"),
        make_doc("edge", "2022-12-31"),
        make_doc("after", "2023-01-01"),
    ]
    pre, post = temporal_split(docs, date(2022, 12, 31))
    assert [d.document_id for d in pre] == ["before", "edge"]
    assert [d.document_id for d in post] == ["after"]


def test_split_is_deterministic():
    docs = [
        make_doc("b", "2022-01-01"),
        make_doc("a", "2022-01-01"),
    ]
    pre1, _ = temporal_split(docs, date(2022, 12, 31))
    pre2, _ = temporal_split(list(reversed(docs)), date(2022, 12, 31))
    assert [d.document_id for d in pre1] == [d.document_id for d in pre2]


def test_agent_facing_backend_never_exposes_post_cutoff_documents():
    cutoff = date(2022, 12, 31)
    backend = LocalFrozenCorpusBackend(
        [make_doc("pre", "2022-12-31"), make_doc("post", "2023-01-01")],
        cutoff=cutoff,
    )
    env = CounterGapEnv(backend=backend, cutoff=cutoff)

    results = env.step(Action(type=ActionType.SEARCH, payload={"query": "pre"}))

    assert [document["document_id"] for document in results["results"]] == ["pre"]
    with pytest.raises(KeyError):
        backend.read("post")
    with pytest.raises(PermissionError):
        env.step(Action(type=ActionType.READ, payload={"document_id": "post"}))


def test_jsonl_backend_filters_post_cutoff_documents(tmp_path):
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_text(
        "\n".join([
            make_doc("pre", "2022-12-31").model_dump_json(),
            make_doc("post", "2023-01-01").model_dump_json(),
        ]) + "\n",
        encoding="utf-8",
    )

    backend = LocalFrozenCorpusBackend.from_jsonl(corpus_path, date(2022, 12, 31))

    assert [document.document_id for document in backend.search("pre")] == ["pre"]
    with pytest.raises(KeyError):
        backend.read("post")
