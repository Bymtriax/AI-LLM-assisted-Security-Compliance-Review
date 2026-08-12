"""Interactively test retrieval against the local S17 ChromaDB experiment."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import chromadb
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "data/vector_db/s17_chroma_experiment"
MANIFEST_PATH = DATABASE_DIR / "manifest.json"
COLLECTION_NAME = "s17_en_v8_2_experiment"
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
DEFAULT_RESULT_COUNT = 3


def embed_query(query: str, api_key: str, model: str) -> list[float]:
    """Convert one user query to a vector with the model used during building."""
    request = Request(
        EMBEDDING_API_URL,
        data=json.dumps({"model": model, "input": query}).encode("utf-8"),
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
    if not isinstance(data, list) or len(data) != 1:
        raise RuntimeError("Embedding API did not return exactly one query vector.")

    vector = data[0].get("embedding")
    if not isinstance(vector, list) or not vector:
        raise RuntimeError("Embedding API returned an empty or invalid query vector.")
    return vector


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        raise SystemExit("Set SILICONFLOW_API_KEY in the project's .env file before running this script.")
    if not MANIFEST_PATH.exists():
        raise SystemExit("S17 ChromaDB experiment not found. Run build_s17_chroma_db.py first.")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    model = str(manifest["embedding_model"])
    client = chromadb.PersistentClient(path=str(DATABASE_DIR))
    collection = client.get_collection(COLLECTION_NAME)
    if collection.count() == 0:
        raise SystemExit("The S17 collection is empty. Run build_s17_chroma_db.py first.")

    print("S17 ChromaDB retrieval test")
    print(f"Collection: {COLLECTION_NAME} ({collection.count()} chunks)")
    print("Enter an English question. Type 'exit' to quit.\n")

    while True:
        query = input("Question > ").strip()
        if query.lower() in {"exit", "quit"}:
            print("Finished.")
            return
        if not query:
            print("Please enter a non-empty question.\n")
            continue

        query_vector = embed_query(query, api_key, model)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=DEFAULT_RESULT_COUNT,
            include=["documents", "metadatas", "distances"],
        )

        print("\nMost relevant S17 chunks (smaller cosine distance = more similar):")
        for rank, (chunk_id, document, metadata, distance) in enumerate(
            zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ),
            start=1,
        ):
            print(f"\n[{rank}] {chunk_id}")
            print(f"Section: {metadata['section']}")
            print(f"Parent sections: {metadata['parent_titles']}")
            print(
                "Source: "
                f"S17 v{metadata['version']}, PDF page {metadata['pdf_page_start']} "
                f"(printed page {metadata['printed_page_start'] or 'N/A'})"
            )
            print(f"Cosine distance: {distance:.4f}")
            print(f"Text: {document}")
        print()


if __name__ == "__main__":
    main()
