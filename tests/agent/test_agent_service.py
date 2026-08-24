"""Tests for the basic Agent conversation service."""

import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import agent_service


def test_respond_sends_history_and_stores_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []

    def fake_generate_messages(messages: list[object]) -> str:
        prompts.append(
            "\n".join(
                f"{message.role}: {message.content}" for message in messages
            )
        )
        return json.dumps(
            {"type": "answer", "content": f"reply-{len(prompts)}"}
        )

    monkeypatch.setattr(
        agent_service,
        "generate_messages",
        fake_generate_messages,
    )
    service = agent_service.AgentService()

    assert service.respond("first question") == "reply-1"
    assert service.respond("follow-up question") == "reply-2"
    assert prompts == [
        (
            f"system: {agent_service.SYSTEM_MESSAGE.content}"
            "\nuser: first question"
        ),
        (
            f"system: {agent_service.SYSTEM_MESSAGE.content}"
            "\nuser: first question"
            "\nassistant: reply-1"
            "\nuser: follow-up question"
        ),
    ]


def test_respond_retrieves_evidence_without_storing_internal_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[object]] = []

    def fake_generate_messages(messages: list[object]) -> str:
        calls.append(list(messages))
        if len(calls) == 1:
            return json.dumps(
                {
                    "type": "tool_call",
                    "tool": "retrieve_regulations",
                    "arguments": {"text": "password requirements"},
                }
            )
        return json.dumps(
            {"type": "answer", "content": "Passwords must be protected."}
        )

    class FakeRAGService:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def retrieve(self, text: str) -> list[str]:
            self.queries.append(text)
            return ["Clause one.", "Clause two."]

    monkeypatch.setattr(
        agent_service,
        "generate_messages",
        fake_generate_messages,
    )
    service = agent_service.AgentService()
    fake_rag = FakeRAGService()
    service._rag = fake_rag  # type: ignore[assignment]

    answer = service.respond("How should passwords be stored?")

    assert answer == "Passwords must be protected."
    assert fake_rag.queries == ["password requirements"]
    assert "Regulation search: password requirements" in calls[1][-1].content  # type: ignore[attr-defined]
    assert "Clause one.\n\nClause two." in calls[1][-1].content  # type: ignore[attr-defined]
    assert [(message.role, message.content) for message in service._messages] == [
        ("user", "How should passwords be stored?"),
        (
            "system",
            "Regulation search: password requirements\n"
            "Search results:\nClause one.\n\nClause two.",
        ),
        ("assistant", "Passwords must be protected."),
    ]

    visible_messages = service.messages
    visible_messages.clear()
    assert len(service.messages) == 3
