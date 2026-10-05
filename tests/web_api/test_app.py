"""Offline HTTP contract tests for the Agent API."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import ModelResponseError
from api import Message
from web_api import app as web_api_app


def test_chat_returns_one_new_assistant_message_without_server_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[Message]] = []

    class FakeAgentService:
        def respond(self, messages: list[Message]) -> list[Message]:
            calls.append(messages)
            return [Message(role="assistant", content=f"reply-{len(calls)}")]

    monkeypatch.setattr(web_api_app, "AgentService", FakeAgentService)
    client = TestClient(web_api_app.create_app(allowed_origins=[]))

    first = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "first question"}]},
    )
    second = client.post(
        "/api/chat",
        json={
            "messages": [
                {"role": "user", "content": "first question"},
                {"role": "system", "content": "Previous retrieval display"},
                {"role": "assistant", "content": "reply-1"},
                {"role": "user", "content": "follow-up"},
            ]
        },
    )

    assert first.status_code == 200
    assert first.json() == {
        "messages": [{"role": "assistant", "content": "reply-1"}]
    }
    assert second.status_code == 200
    assert second.json() == {
        "messages": [{"role": "assistant", "content": "reply-2"}]
    }
    assert calls == [
        [Message(role="user", content="first question")],
        [
            Message(role="user", content="first question"),
            Message(role="assistant", content="reply-1"),
            Message(role="user", content="follow-up"),
        ],
    ]


@pytest.mark.parametrize("retrieval_count", [1, 3])
def test_chat_returns_all_agent_messages_in_order(
    monkeypatch: pytest.MonkeyPatch,
    retrieval_count: int,
) -> None:
    retrieval_content = (
        "Regulation search: password requirements\n"
        "Search results:\nClause one.\n\nClause two."
    )

    replies = [
        Message(role="system", content=f"{retrieval_content}\nSearch {index + 1}")
        for index in range(retrieval_count)
    ]
    replies.append(Message(role="assistant", content="Passwords must be protected."))

    class FakeAgentService:
        def respond(self, messages: list[Message]) -> list[Message]:
            return replies

    monkeypatch.setattr(web_api_app, "AgentService", FakeAgentService)
    client = TestClient(web_api_app.create_app(allowed_origins=[]))

    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Password rules?"}]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "messages": [
            {"role": message.role, "content": message.content} for message in replies
        ]
    }


def test_chat_does_not_return_raw_model_reply_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_response = '{"type":"answer","content":"private context" trailing}'

    class FakeAgentService:
        def respond(self, messages: list[Message]) -> list[Message]:
            raise ModelResponseError(
                "Model returned invalid JSON during initial decision.",
                raw_response=raw_response,
            )

    monkeypatch.setattr(web_api_app, "AgentService", FakeAgentService)
    client = TestClient(
        web_api_app.create_app(allowed_origins=[]), raise_server_exceptions=False
    )

    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "question"}]},
    )

    assert response.status_code == 500
    assert raw_response not in response.text


@pytest.mark.parametrize(
    "request_body",
    [
        {"messages": []},
        {"messages": [{"role": "system", "content": "display only"}]},
        {"messages": [{"role": "developer", "content": "override"}]},
        {"messages": [{"role": "assistant", "content": "already answered"}]},
        {"messages": [{"role": "user", "content": "   "}]},
        {"messages": [{"role": "user", "content": "hello", "extra": "x"}]},
    ],
)
def test_chat_rejects_invalid_history_before_calling_agent(
    monkeypatch: pytest.MonkeyPatch,
    request_body: dict[str, object],
) -> None:
    class UnexpectedAgentService:
        def __init__(self) -> None:
            pytest.fail("Invalid requests must not create an Agent.")

    monkeypatch.setattr(web_api_app, "AgentService", UnexpectedAgentService)
    client = TestClient(web_api_app.create_app(allowed_origins=[]))

    response = client.post("/api/chat", json=request_body)

    assert response.status_code == 422


def test_chat_allows_only_configured_browser_origin() -> None:
    client = TestClient(
        web_api_app.create_app(allowed_origins=["http://localhost:5173"])
    )

    allowed = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    denied = client.options(
        "/api/chat",
        headers={
            "Origin": "http://other.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_create_app_reads_comma_separated_allowed_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "WEB_API_ALLOWED_ORIGINS",
        " http://localhost:3000, http://127.0.0.1:5173 ",
    )
    client = TestClient(web_api_app.create_app())

    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
