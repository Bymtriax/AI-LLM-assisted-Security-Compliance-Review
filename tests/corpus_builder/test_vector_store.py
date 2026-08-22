"""QA tests for the local vector_store module; no embedding API is called."""

from __future__ import annotations

import sys
from hashlib import sha256
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder import vector_store
from corpus_builder.models import CorpusRecord


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point the real module to a new temporary ChromaDB for each test."""
    monkeypatch.setattr(vector_store, "DATABASE_DIR", tmp_path / "vector_db")
    monkeypatch.setattr(vector_store, "COLLECTION_NAME", "test_security_standards")
    return vector_store


def retrieval_text(body: str, section: str = "15.2.2") -> str:
    return "\n".join(
        [
            f"Section: {section}",
            "Parent sections: 15. COMMUNICATIONS SECURITY",
            f"Text: {body}",
        ]
    )


def record(chunk_id: str, body: str) -> CorpusRecord:
    return CorpusRecord(
        id=chunk_id,
        text=retrieval_text(body),
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


def test_store_one_vector_and_query_it(store) -> None:
    """One stored record is retrieved as a typed nearest result."""
    original = record("s17-15.2.2", "Encrypt confidential data in transit.")
    store.store_vector(original, [1.0, 0.0])

    results = store.query_vectors([1.0, 0.0])

    assert len(results) == 1
    assert isinstance(results[0], CorpusRecord)
    assert results[0].id == original.id
    assert results[0].text == original.text
    assert results[0].metadata == original.metadata


def test_store_and_query_round_trip_all_metadata(store) -> None:
    text = retrieval_text("Encrypt confidential data in transit.")
    original = CorpusRecord(
        id="s17-15.2.2-part-01",
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
            "parent_chunk_id": "s17-15.2.2-clause",
            "part_number": 1,
            "part_count": 2,
            "source_kind": "numbered_clause",
            "split_method": "sentence_boundary",
            "word_count": 5,
            "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        },
    )
    store.store_vector(original, [1.0, 0.0])

    results = store.query_vectors([1.0, 0.0])

    assert results[0].metadata == original.metadata


def test_store_multiple_vectors_and_return_top_three(store) -> None:
    """Batch records and vectors keep their pairing and retrieval order."""
    store.store_vectors(
        [
            record("encryption", "Encrypt data."),
            record("logging", "Keep audit logs."),
            record("access", "Control user access."),
        ],
        [[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]],
    )

    results = store.query_vectors([1.0, 0.0], top_k=3)

    assert [result.id for result in results] == ["encryption", "access", "logging"]


def test_mismatched_record_and_vector_counts_are_rejected(store) -> None:
    with pytest.raises(ValueError, match="same length"):
        store.store_vectors([record("one", "One regulation.")], [])


def test_invalid_query_arguments_are_rejected(store) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        store.query_vectors([])
    with pytest.raises(ValueError, match="at least 1"):
        store.query_vectors([1.0, 0.0], top_k=0)


def test_empty_store_and_excessive_top_k_return_available_results(store) -> None:
    assert store.query_vectors([1.0, 0.0]) == []

    store.store_vector(record("one", "One corpus passage."), [1.0, 0.0])

    assert [result.id for result in store.query_vectors([1.0, 0.0], top_k=99)] == ["one"]
