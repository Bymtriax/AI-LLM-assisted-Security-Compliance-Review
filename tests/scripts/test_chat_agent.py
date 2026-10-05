"""Offline test for the terminal Agent chat script."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts/chat_agent.py"
SPEC = importlib.util.spec_from_file_location("chat_agent", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
chat_agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(chat_agent)

from api import Message


def test_main_reuses_one_agent_until_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: list[list[Message]] = []
    input_prompts: list[str] = []
    inputs = iter(["first message", "follow-up", "third question", "exit"])

    class FakeAgentService:
        def respond(self, messages: list[Message]) -> list[Message]:
            received.append(list(messages))
            replies: list[Message] = []
            if messages[-1].content == "follow-up":
                replies.append(
                    Message(
                        role="system",
                        content="Regulation search: follow-up\nSearch results:\nClause.",
                    )
                )
            replies.append(Message(role="assistant", content=f"reply-{len(received)}"))
            return replies

    monkeypatch.setattr(chat_agent, "AgentService", FakeAgentService)
    def fake_input(prompt: str) -> str:
        input_prompts.append(prompt)
        return next(inputs)

    monkeypatch.setattr("builtins.input", fake_input)

    chat_agent.main()

    assert received == [
        [Message(role="user", content="first message")],
        [
            Message(role="user", content="first message"),
            Message(role="assistant", content="reply-1"),
            Message(role="user", content="follow-up"),
        ],
        [
            Message(role="user", content="first message"),
            Message(role="assistant", content="reply-1"),
            Message(role="user", content="follow-up"),
            Message(role="assistant", content="reply-2"),
            Message(role="user", content="third question"),
        ],
    ]
    assert input_prompts == [
        f"{chat_agent.GREEN}You:{chat_agent.RESET} ",
        f"{chat_agent.GREEN}You:{chat_agent.RESET} ",
        f"{chat_agent.GREEN}You:{chat_agent.RESET} ",
        f"{chat_agent.GREEN}You:{chat_agent.RESET} ",
    ]
    assert capsys.readouterr().out.splitlines() == [
        "Chat with the security compliance Agent. Type exit or quit to stop.",
        f"{chat_agent.BLUE}Agent:{chat_agent.RESET} reply-1",
        (
            f"{chat_agent.YELLOW}System: Regulation search: follow-up"
        ),
        "Search results:",
        f"Clause.{chat_agent.RESET}",
        f"{chat_agent.BLUE}Agent:{chat_agent.RESET} reply-2",
        f"{chat_agent.BLUE}Agent:{chat_agent.RESET} reply-3",
    ]


def test_main_does_not_keep_a_failed_turn_in_history(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(["What does S17 say?", "try again", "exit"])
    received: list[list[Message]] = []

    class FakeAgentService:
        def respond(self, messages: list[Message]) -> list[Message]:
            received.append(list(messages))
            if messages[-1].content == "try again":
                return [Message(role="assistant", content="Successful retry.")]
            raise chat_agent.ModelResponseError(
                "Model returned empty content during answer after regulation retrieval.",
                raw_response="",
            )

    monkeypatch.setattr(chat_agent, "AgentService", FakeAgentService)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    chat_agent.main()

    assert received == [
        [Message(role="user", content="What does S17 say?")],
        [Message(role="user", content="try again")],
    ]
    assert capsys.readouterr().out.splitlines() == [
        "Chat with the security compliance Agent. Type exit or quit to stop.",
        "Error: Model returned empty content during answer after regulation retrieval.",
        "Raw model reply: ''",
        f"{chat_agent.BLUE}Agent:{chat_agent.RESET} Successful retry.",
    ]


def test_main_shows_raw_initial_model_reply_on_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(["what is security", "exit"])
    raw_response = '{"type":"answer","content":"A "security" topic"}'

    class FakeAgentService:
        def respond(self, messages: list[Message]) -> list[Message]:
            assert messages == [Message(role="user", content="what is security")]
            raise chat_agent.ModelResponseError(
                "Model returned invalid JSON during initial decision.",
                raw_response=raw_response,
            )

    monkeypatch.setattr(chat_agent, "AgentService", FakeAgentService)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    chat_agent.main()

    assert capsys.readouterr().out.splitlines() == [
        "Chat with the security compliance Agent. Type exit or quit to stop.",
        "Error: Model returned invalid JSON during initial decision.",
        f"Raw model reply: {raw_response!r}",
    ]
