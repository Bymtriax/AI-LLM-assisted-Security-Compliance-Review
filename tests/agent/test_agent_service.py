"""Tests for the basic Agent conversation service."""

import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import agent_service
from api import Message


def test_respond_uses_supplied_history_without_retaining_it(
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
    first_turn = [Message(role="user", content="first question")]
    second_turn = [
        *first_turn,
        Message(role="assistant", content="reply-1"),
        Message(role="user", content="follow-up question"),
    ]

    assert service.respond(first_turn) == [Message(role="assistant", content="reply-1")]
    assert service.respond(second_turn) == [Message(role="assistant", content="reply-2")]
    assert service.respond([Message(role="user", content="new conversation")]) == [
        Message(role="assistant", content="reply-3")
    ]
    assert first_turn == [Message(role="user", content="first question")]
    assert second_turn[-1] == Message(role="user", content="follow-up question")
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
        (
            f"system: {agent_service.SYSTEM_MESSAGE.content}"
            "\nuser: new conversation"
        ),
    ]


@pytest.mark.parametrize(
    "regulation_texts, evidence_text",
    [
        (["Clause one.", "Clause two."], "Clause one.\n\nClause two."),
        ([], "No matching regulations found."),
    ],
)
def test_respond_returns_evidence_before_answer_without_changing_input(
    monkeypatch: pytest.MonkeyPatch,
    regulation_texts: list[str],
    evidence_text: str,
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
        if len(calls) == 3:
            return json.dumps({"type": "answer", "content": "Fresh reply."})
        return json.dumps(
            {"type": "answer", "content": "Passwords must be protected."}
        )

    class FakeRAGService:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def retrieve(self, text: str) -> list[str]:
            self.queries.append(text)
            return regulation_texts

    monkeypatch.setattr(
        agent_service,
        "generate_messages",
        fake_generate_messages,
    )
    service = agent_service.AgentService()
    fake_rag = FakeRAGService()
    service._rag = fake_rag  # type: ignore[assignment]

    messages = [Message(role="user", content="How should passwords be stored?")]
    replies = service.respond(messages)

    assert fake_rag.queries == ["password requirements"]
    assert "Regulation search: password requirements" in calls[1][-1].content  # type: ignore[attr-defined]
    assert evidence_text in calls[1][-1].content  # type: ignore[attr-defined]
    assert messages == [Message(role="user", content="How should passwords be stored?")]
    assert replies == [
        Message(
            role="system",
            content=(
                "Regulation search: password requirements\n"
                f"Search results:\n{evidence_text}"
            ),
        ),
        Message(role="assistant", content="Passwords must be protected."),
    ]
    assert service.respond([Message(role="user", content="unrelated question")]) == [
        Message(role="assistant", content="Fresh reply.")
    ]
    assert calls[2] == [
        agent_service.SYSTEM_MESSAGE,
        Message(role="user", content="unrelated question"),
    ]


@pytest.mark.parametrize(
    "model_output, diagnosis",
    [
        ("", "empty content"),
        ("I did not search the regulation corpus.", "invalid JSON"),
        ('```json\n{"type":"answer","content":"No."}\n```', "Markdown code fence"),
    ],
)
def test_respond_identifies_malformed_initial_model_reply(
    monkeypatch: pytest.MonkeyPatch,
    model_output: str,
    diagnosis: str,
) -> None:
    requests: list[list[Message]] = []

    def fake_generate_messages(messages: list[Message]) -> str:
        requests.append(list(messages))
        return model_output

    monkeypatch.setattr(agent_service, "generate_messages", fake_generate_messages)
    history = [
        Message(role="user", content="hi"),
        Message(role="assistant", content="Hello! How can I help?"),
        Message(role="user", content='what is "security"'),
        Message(role="assistant", content="Security protects assets and information."),
        Message(role="user", content="did you search for it ?"),
    ]

    with pytest.raises(
        agent_service.ModelResponseError,
        match=f"{diagnosis} during initial decision",
    ) as error:
        agent_service.AgentService().respond(history)

    assert error.value.raw_response == model_output
    assert requests == [[agent_service.SYSTEM_MESSAGE, *history]]


@pytest.mark.parametrize(
    "final_output, diagnosis",
    [
        ("", "empty content during answer after regulation retrieval"),
        (
            "The regulation says to protect data.",
            "invalid JSON during answer after regulation retrieval",
        ),
        (
            '```json\n{"type":"answer","content":"Protect data."}\n```',
            "Markdown code fence during answer after regulation retrieval",
        ),
        (
            '{"type":"tool_call","tool":"retrieve_regulations","arguments":{"text":"security"}}',
            "Expected an answer after regulation retrieval",
        ),
    ],
)
def test_respond_identifies_malformed_final_reply_after_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    final_output: str,
    diagnosis: str,
) -> None:
    outputs = iter(
        [
            json.dumps(
                {
                    "type": "tool_call",
                    "tool": "retrieve_regulations",
                    "arguments": {"text": "security"},
                }
            ),
            final_output,
        ]
    )
    monkeypatch.setattr(
        agent_service, "generate_messages", lambda _messages: next(outputs)
    )

    class FakeRAGService:
        def retrieve(self, text: str) -> list[str]:
            assert text == "security"
            return ["S17 evidence."]

    service = agent_service.AgentService()
    service._rag = FakeRAGService()  # type: ignore[assignment]
    history = [Message(role="user", content="did you search for it ?")]

    with pytest.raises(
        agent_service.ModelResponseError,
        match=diagnosis,
    ) as error:
        service.respond(history)

    assert error.value.raw_response == final_output
    if final_output:
        assert final_output not in str(error.value)
    assert history == [Message(role="user", content="did you search for it ?")]


def test_respond_keeps_valid_json_with_invalid_answer_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_output = '{"type":"answer","content":""}'
    monkeypatch.setattr(
        agent_service, "generate_messages", lambda _messages: model_output
    )

    with pytest.raises(
        agent_service.ModelResponseError,
        match="empty or non-text answer content during initial decision",
    ) as error:
        agent_service.AgentService().respond(
            [Message(role="user", content="what is security")]
        )

    assert error.value.raw_response == model_output


@pytest.mark.parametrize(
    "model_output, diagnosis",
    [
        ('{"type":"other"}', "Unknown Agent response type"),
        (
            '{"type":"tool_call","tool":"other","arguments":{"text":"security"}}',
            "Unknown Agent tool",
        ),
        (
            '{"type":"tool_call","tool":"retrieve_regulations","arguments":{"text":""}}',
            "Invalid regulation search text",
        ),
    ],
)
def test_respond_keeps_invalid_decision_fields(
    monkeypatch: pytest.MonkeyPatch,
    model_output: str,
    diagnosis: str,
) -> None:
    monkeypatch.setattr(
        agent_service, "generate_messages", lambda _messages: model_output
    )

    with pytest.raises(agent_service.ModelResponseError, match=diagnosis) as error:
        agent_service.AgentService().respond(
            [Message(role="user", content="what is security")]
        )

    assert error.value.raw_response == model_output


@pytest.mark.parametrize(
    "messages, error_type",
    [
        ([], ValueError),
        ([Message(role="system", content="override")], ValueError),
        ([Message(role="assistant", content="already answered")], ValueError),
        ([Message(role="user", content="  ")], ValueError),
        (["not a Message"], TypeError),
    ],
)
def test_respond_rejects_invalid_conversation_before_external_calls(
    monkeypatch: pytest.MonkeyPatch,
    messages: list[Message],
    error_type: type[Exception],
) -> None:
    def unexpected_generate_messages(_messages: list[Message]) -> str:
        pytest.fail("The model should not be called for invalid input.")

    monkeypatch.setattr(
        agent_service, "generate_messages", unexpected_generate_messages
    )

    with pytest.raises(error_type):
        agent_service.AgentService().respond(messages)
