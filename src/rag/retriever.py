"""Retrieve regulation texts that are most relevant to a query."""

from __future__ import annotations

from api import embedded_api
from corpus_builder import vector_store


class Retriever:
    """Run vector retrieval with one configured result limit."""

    def __init__(self, top_k: int = 3) -> None:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k must be a positive integer.")
        self._top_k = top_k

    def retrieve(self, text: str) -> list[str]:
        """Return matching regulation texts from most to least relevant."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Retrieval text must be a non-empty string.")

        query_vector = embedded_api.embed_text(text)
        records = vector_store.query_vectors(query_vector, top_k=self._top_k)
        return [record.text for record in records]
