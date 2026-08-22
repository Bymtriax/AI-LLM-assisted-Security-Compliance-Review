"""Ask questions and print the three nearest corpus records in the vector database."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api import embedded_api
from corpus_builder import vector_store


def main() -> None:
    print("Ask a question about the regulations. Press Enter or type 'exit' to quit.")

    while True:
        question = input("\nQuestion: ").strip()
        if not question or question.lower() == "exit":
            break

        query_vector = embedded_api.embed_text(question)
        results = vector_store.query_vectors(query_vector, top_k=3)

        if not results:
            print("The vector database is empty.")
            continue

        for rank, result in enumerate(results, start=1):
            print(f"\n{rank}. {result.id}")
            print(result.text)


if __name__ == "__main__":
    main()
