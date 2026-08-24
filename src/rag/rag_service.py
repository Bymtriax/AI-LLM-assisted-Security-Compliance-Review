"""Service boundary between the Agent and regulation retrieval."""

from __future__ import annotations

from rag.retriever import Retriever


class RAGService:
    """Expose regulation retrieval to the Agent."""

    def __init__(self, retriever: Retriever | None = None) -> None:
        self._retriever = retriever if retriever is not None else Retriever()

    def retrieve(self, question_text: str) -> list[str]:
        """Return matching regulation texts from most to least relevant."""
        return self._retriever.retrieve(question_text)
