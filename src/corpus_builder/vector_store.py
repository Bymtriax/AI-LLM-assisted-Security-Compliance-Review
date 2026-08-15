"""Store and query regulation vectors with local ChromaDB."""

from __future__ import annotations

from pathlib import Path

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "data/vector_db/chroma"
COLLECTION_NAME = "security_standards"


def store_vector(record: dict[str, object], vector: list[float]) -> None:
    """Store one regulation record and its vector."""
    store_vectors([record], [vector])


def store_vectors(records: list[dict[str, object]], vectors: list[list[float]]) -> None:
    """Store regulation records and vectors in matching order."""
    if len(records) != len(vectors):
        raise ValueError("Records and vectors must have the same length.")
    if not records:
        return

    ids, texts, metadatas = zip(*(_record_parts(record) for record in records))
    _collection().upsert(
        ids=list(ids),
        embeddings=vectors,
        documents=list(texts),
        metadatas=list(metadatas),
    )


def query_vectors(vector: list[float], top_k: int = 3) -> list[dict[str, object]]:
    """Return up to top_k regulation records nearest to one query vector."""
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
        include=["documents", "metadatas", "distances"],
    )
    return [
        {
            "id": chunk_id,
            "text": text,
            "metadata": metadata,
            "distance": distance,
        }
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
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


def _record_parts(record: dict[str, object]) -> tuple[str, str, dict[str, str | int | float | bool]]:
    """Validate and unpack the record shape required by ChromaDB."""
    try:
        chunk_id = str(record["id"])
        text = str(record["text"])
        metadata = dict(record["metadata"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Each record needs id, text and metadata.") from error

    if not chunk_id or not text:
        raise ValueError("Record id and text cannot be empty.")
    return chunk_id, text, metadata
