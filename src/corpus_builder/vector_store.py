"""Store and query regulation vectors with local ChromaDB."""

from __future__ import annotations

from pathlib import Path

import chromadb

from corpus_builder.models import CorpusRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "data/vector_db/chroma"
COLLECTION_NAME = "security_standards"


def store_vector(record: CorpusRecord, vector: list[float]) -> None:
    """Store one corpus record and its vector."""
    store_vectors([record], [vector])


def store_vectors(records: list[CorpusRecord], vectors: list[list[float]]) -> None:
    """Store corpus records and vectors in matching order."""
    if len(records) != len(vectors):
        raise ValueError("Records and vectors must have the same length.")
    if not records:
        return

    _collection().upsert(
        ids=[record.id for record in records],
        embeddings=vectors,
        documents=[record.text for record in records],
        metadatas=[dict(record.metadata) for record in records],
    )


def query_vectors(vector: list[float], top_k: int = 3) -> list[CorpusRecord]:
    """Return up to top_k nearest corpus records in similarity-rank order."""
    if not vector:
        raise ValueError("Query vector cannot be empty.")
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    collection = _collection()
    if collection.count() == 0:
        return []

    result = collection.query(
        query_embeddings=[vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas"],
    )
    return [
        CorpusRecord(id=chunk_id, text=text, metadata=metadata)
        for chunk_id, text, metadata in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
        )
    ]


def _collection() -> chromadb.Collection:
    """Open the one persistent project collection."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DATABASE_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
    )
