"""QA tests for the Agent-facing RAG service."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag.rag_service import RAGService


class FakeRetriever:
    def __init__(self) -> None:
        self.received_text: str | None = None

    def retrieve(self, text: str) -> list[str]:
        self.received_text = text
        return ["Most relevant clause.", "Less relevant clause."]


def test_rag_service_passes_agent_question_to_retriever() -> None:
    fake_retriever = FakeRetriever()
    service = RAGService(retriever=fake_retriever)  # type: ignore[arg-type]

    results = service.retrieve("How should confidential data be protected?")

    assert fake_retriever.received_text == "How should confidential data be protected?"
    assert results == ["Most relevant clause.", "Less relevant clause."]
