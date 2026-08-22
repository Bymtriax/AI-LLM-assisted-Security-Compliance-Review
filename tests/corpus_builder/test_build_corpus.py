"""Tests for the shared corpus-build entry program."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api import embedded_api
from corpus_builder import build_corpus, vector_store
from corpus_builder.models import CorpusRecord


def record(record_id: str, text: str, section: str) -> CorpusRecord:
    parent_titles = "15. COMMUNICATIONS SECURITY"
    return CorpusRecord(
        id=record_id,
        text=f"Section: {section}\nParent sections: {parent_titles}\nText: {text}",
        metadata={
            "document": "S17",
            "version": "8.2",
            "language": "en",
            "section": section,
            "parent_titles": parent_titles,
            "source_file": "S17.pdf",
            "pdf_page_start": 33,
            "printed_page_start": "27",
        },
    )


def test_build_corpus_combines_handlers_embeds_and_stores_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = record("s17-one", "Encrypt data in transit.", "15.2.2")
    second = record("s17-two", "Retain audit logs.", "12.4.1")
    received: dict[str, object] = {}

    def fake_embed(texts: list[str]) -> list[list[float]]:
        received["texts"] = texts
        return [[1.0, 0.0], [0.0, 1.0]]

    def fake_store(records: list[CorpusRecord], vectors: list[list[float]]) -> None:
        received["records"] = records
        received["vectors"] = vectors

    monkeypatch.setattr(embedded_api, "embed_texts", fake_embed)
    monkeypatch.setattr(vector_store, "store_vectors", fake_store)

    result = build_corpus.build_corpus([lambda: [first], lambda: [second]])

    assert result == [first, second]
    assert received["texts"] == [first.text, second.text]
    assert received["records"] == [first, second]
    assert received["vectors"] == [[1.0, 0.0], [0.0, 1.0]]


def test_build_corpus_rejects_duplicate_ids_before_embedding_or_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = record("same-id", "First record.", "1")
    duplicate_again = record("same-id", "Second record.", "2")
    monkeypatch.setattr(
        embedded_api,
        "embed_texts",
        lambda texts: pytest.fail("Embedding must not start when IDs are duplicated."),
    )
    monkeypatch.setattr(
        vector_store,
        "store_vectors",
        lambda records, vectors: pytest.fail("Storage must not start when IDs are duplicated."),
    )

    with pytest.raises(ValueError, match="duplicate"):
        build_corpus.build_corpus([lambda: [duplicate], lambda: [duplicate_again]])
