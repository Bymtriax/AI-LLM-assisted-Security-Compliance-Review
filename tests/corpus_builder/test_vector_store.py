"""QA tests for the local vector_store module; no embedding API is called."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder import vector_store


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point the real module to a new temporary ChromaDB for each test."""
    monkeypatch.setattr(vector_store, "DATABASE_DIR", tmp_path / "vector_db")
    monkeypatch.setattr(vector_store, "COLLECTION_NAME", "test_security_standards")
    return vector_store


def record(chunk_id: str, text: str) -> dict[str, object]:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {"document": "S17", "section": "15.2.2"},
    }


def test_store_one_vector_and_query_it(store) -> None:
    """One stored record can be retrieved as the nearest result."""
    store.store_vector(record("s17-15.2.2", "Encrypt confidential data in transit."), [1.0, 0.0])

    results = store.query_vectors([1.0, 0.0])

    assert len(results) == 1
    assert results[0]["id"] == "s17-15.2.2"
    assert results[0]["text"] == "Encrypt confidential data in transit."
    assert results[0]["metadata"]["section"] == "15.2.2"
    assert results[0]["distance"] == pytest.approx(0.0)


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

    assert [result["id"] for result in results] == ["encryption", "access", "logging"]


def test_mismatched_record_and_vector_counts_are_rejected(store) -> None:
    with pytest.raises(ValueError, match="same length"):
        store.store_vectors([record("one", "One regulation.")], [])


def test_invalid_query_arguments_are_rejected(store) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        store.query_vectors([])
    with pytest.raises(ValueError, match="at least 1"):
        store.query_vectors([1.0, 0.0], top_k=0)
