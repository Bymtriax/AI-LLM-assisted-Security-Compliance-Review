"""QA tests for the RAG retriever; no real embedding API or database is used."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder.models import CorpusRecord
from rag import retriever


def record(record_id: str, text: str) -> CorpusRecord:
    return CorpusRecord(
        id=record_id,
        text=text,
        metadata={
            "document": "S17",
            "version": "8.2",
            "language": "en",
            "section": "15.2.2",
            "parent_titles": "15. COMMUNICATIONS SECURITY",
            "source_file": "S17.pdf",
            "pdf_page_start": 33,
            "printed_page_start": "27",
        },
    )


def test_retrieve_embeds_query_and_returns_ranked_texts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def fake_embed_text(text: str) -> list[float]:
        received["embedding_text"] = text
        return [1.0, 0.0]

    def fake_query_vectors(vector: list[float], top_k: int) -> list[CorpusRecord]:
        received["query_vector"] = vector
        received["top_k"] = top_k
        return [
            record("most-relevant", "Most relevant regulation text."),
            record("less-relevant", "Less relevant regulation text."),
        ]

    monkeypatch.setattr(retriever.embedded_api, "embed_text", fake_embed_text)
    monkeypatch.setattr(retriever.vector_store, "query_vectors", fake_query_vectors)

    results = retriever.Retriever(top_k=2).retrieve(
        "How should confidential data be transmitted?"
    )

    assert results == [
        "Most relevant regulation text.",
        "Less relevant regulation text.",
    ]
    assert received == {
        "embedding_text": "How should confidential data be transmitted?",
        "query_vector": [1.0, 0.0],
        "top_k": 2,
    }


def test_retrieve_returns_empty_list_when_database_has_no_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(retriever.embedded_api, "embed_text", lambda text: [1.0])
    monkeypatch.setattr(
        retriever.vector_store,
        "query_vectors",
        lambda vector, top_k: [],
    )

    assert retriever.Retriever().retrieve("valid query") == []


@pytest.mark.parametrize("text", ["", "   ", "\n\t", None, 123])
def test_retrieve_rejects_invalid_text_before_external_calls(
    monkeypatch: pytest.MonkeyPatch,
    text: object,
) -> None:
    monkeypatch.setattr(
        retriever.embedded_api,
        "embed_text",
        lambda value: pytest.fail("Invalid input must not call the embedding API."),
    )

    with pytest.raises(ValueError, match="non-empty string"):
        retriever.Retriever().retrieve(text)  # type: ignore[arg-type]


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_retriever_rejects_invalid_top_k_during_creation(
    top_k: object,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        retriever.Retriever(top_k=top_k)  # type: ignore[arg-type]
