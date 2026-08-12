"""Build a persistent ChromaDB collection from the audited S17 V2 chunks."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import chromadb
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_JSONL = PROJECT_ROOT / "exp/output/s17_en_retrieval_chunks_v2.jsonl"
DATABASE_DIR = PROJECT_ROOT / "data/vector_db/s17_chroma_experiment"
MANIFEST_PATH = DATABASE_DIR / "manifest.json"

COLLECTION_NAME = "s17_en_v8_2_experiment"
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
EMBEDDING_MODEL = "Qwen/Qwen3-VL-Embedding-8B"
# SiliconFlow returns response indexes 0-7 for a batch of eight.  Larger
# requests are internally split and restart those indexes, so eight preserves
# a one-to-one, directly verifiable response-index mapping.
BATCH_SIZE = 8
TEST_QUERY = "What does S17 require for encryption when transmitting classified information?"


def load_chunks(jsonl_path: Path) -> list[dict[str, object]]:
    """Load V2 chunks and fail before any API call if their IDs are invalid."""
    chunks = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not chunks:
        raise ValueError("The input JSONL contains no chunks.")

    ids = [str(chunk["id"]) for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("The input JSONL contains duplicate chunk IDs.")
    return chunks


def embedding_text(chunk: dict[str, object]) -> str:
    """Use only the three fields agreed for semantic embedding."""
    parent_titles = " > ".join(str(title) for title in chunk["parent_titles"])
    return "\n".join(
        [
            f"Section: {chunk['section']}",
            f"Parent sections: {parent_titles}",
            f"Text: {chunk['text']}",
        ]
    )


def chroma_metadata(chunk: dict[str, object]) -> dict[str, str | int | float | bool]:
    """Keep non-semantic provenance data available for filtering and citations."""
    return {
        "parent_chunk_id": str(chunk["parent_chunk_id"]),
        "document": str(chunk["document"]),
        "version": str(chunk["version"]),
        "language": str(chunk["language"]),
        "section": str(chunk["section"]),
        "source_kind": str(chunk["source_kind"]),
        "split_method": str(chunk["split_method"]),
        "part_number": int(chunk["part_number"]),
        "part_count": int(chunk["part_count"]),
        "parent_titles": " > ".join(str(title) for title in chunk["parent_titles"]),
        "pdf_page_start": int(chunk["pdf_page_start"]),
        "printed_page_start": str(chunk["printed_page_start"] or ""),
        "word_count": int(chunk["word_count"]),
        "text_sha256": str(chunk["text_sha256"]),
        "source_file": str(chunk["source_file"]),
    }


def embed_texts(texts: list[str], api_key: str) -> list[list[float]]:
    """Request one API batch and validate its response-to-input mapping."""
    request = Request(
        EMBEDDING_API_URL,
        data=json.dumps({"model": EMBEDDING_MODEL, "input": texts}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Embedding API returned HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach embedding API: {error.reason}") from error

    data = payload.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise RuntimeError(
            f"Embedding API returned {len(data) if isinstance(data, list) else 0} vectors "
            f"for {len(texts)} input texts."
        )

    ordered = sorted(data, key=lambda item: item["index"])
    indexes = [item.get("index") for item in ordered]
    if indexes != list(range(len(texts))):
        raise RuntimeError("Embedding API response indexes do not match the input order.")

    vectors = [item.get("embedding") for item in ordered]
    if not all(isinstance(vector, list) and vector for vector in vectors):
        raise RuntimeError("Embedding API returned an empty or invalid vector.")
    return vectors


def batches(items: list[dict[str, object]], size: int) -> list[list[dict[str, object]]]:
    return [items[start : start + size] for start in range(0, len(items), size)]


def write_manifest(chunk_count: int, vector_dimension: int, source_hash: str) -> None:
    manifest = {
        "collection_name": COLLECTION_NAME,
        "source_file": str(INPUT_JSONL.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_sha256": source_hash,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_input_fields": ["section", "parent_titles", "text"],
        "chunk_count": chunk_count,
        "vector_dimension": vector_dimension,
        "batch_size": BATCH_SIZE,
        "built_at_utc": datetime.now(UTC).isoformat(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def existing_ids(collection: chromadb.Collection) -> set[str]:
    """Return existing IDs so an interrupted build can resume without re-embedding."""
    stored = collection.get(include=[])
    return set(stored["ids"])


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        raise SystemExit("Set SILICONFLOW_API_KEY in the project's .env file before running this script.")
    if not INPUT_JSONL.exists():
        raise FileNotFoundError(f"V2 input JSONL not found: {INPUT_JSONL}")

    chunks = load_chunks(INPUT_JSONL)
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DATABASE_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "embedding_model": EMBEDDING_MODEL,
            "distance_metric": "cosine",
        },
        configuration={"hnsw": {"space": "cosine"}},
    )

    stored_ids = existing_ids(collection)
    input_ids = {str(chunk["id"]) for chunk in chunks}
    unexpected_ids = stored_ids - input_ids
    if unexpected_ids:
        raise RuntimeError("The collection contains IDs not present in the current input JSONL.")

    remaining_chunks = [chunk for chunk in chunks if str(chunk["id"]) not in stored_ids]
    expected_dimension: int | None = None
    if stored_ids:
        sample = collection.get(ids=[next(iter(stored_ids))], include=["embeddings"])
        expected_dimension = len(sample["embeddings"][0])
    print(f"Existing chunks: {len(stored_ids)}; remaining chunks: {len(remaining_chunks)}.")

    all_batches = batches(remaining_chunks, BATCH_SIZE)
    for batch_number, chunk_batch in enumerate(all_batches, start=1):
        vectors = embed_texts([embedding_text(chunk) for chunk in chunk_batch], api_key)
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise RuntimeError(f"Batch {batch_number} returned vectors with mixed dimensions: {dimensions}")
        dimension = dimensions.pop()
        if expected_dimension is None:
            expected_dimension = dimension
        elif dimension != expected_dimension:
            raise RuntimeError(
                f"Batch {batch_number} returned dimension {dimension}; expected {expected_dimension}."
            )

        collection.upsert(
            ids=[str(chunk["id"]) for chunk in chunk_batch],
            embeddings=vectors,
            documents=[str(chunk["text"]) for chunk in chunk_batch],
            metadatas=[chroma_metadata(chunk) for chunk in chunk_batch],
        )
        print(f"Stored batch {batch_number}/{len(all_batches)} ({len(chunk_batch)} chunks).")

    if expected_dimension is None:
        raise RuntimeError("No vectors were generated.")
    if collection.count() != len(chunks):
        raise RuntimeError(
            f"Database count is {collection.count()}, but the input contains {len(chunks)} chunks."
        )

    source_hash = sha256(INPUT_JSONL.read_bytes()).hexdigest()
    write_manifest(len(chunks), expected_dimension, source_hash)

    query_vector = embed_texts([TEST_QUERY], api_key)[0]
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )
    ids = result["ids"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    print("\nBuild complete")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Stored chunks: {collection.count()}")
    print(f"Vector dimension: {expected_dimension}")
    print(f"Database directory: {DATABASE_DIR.relative_to(PROJECT_ROOT)}")
    print("\nVerification query results:")
    for rank, (chunk_id, metadata, distance) in enumerate(zip(ids, metadatas, distances), start=1):
        print(f"{rank}. {chunk_id} | section {metadata['section']} | distance {distance:.4f}")


if __name__ == "__main__":
    main()
