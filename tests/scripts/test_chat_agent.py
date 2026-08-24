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
    received: list[str] = []
    input_prompts: list[str] = []
    inputs = iter(["first message", "follow-up", "exit"])

    class FakeAgentService:
        def __init__(self) -> None:
            self.messages: list[Message] = []

        def respond(self, text: str) -> str:
            received.append(text)
            self.messages.append(Message(role="user", content=text))
            if text == "follow-up":
                self.messages.append(
                    Message(
                        role="system",
                        content="Regulation search: follow-up\nSearch results:\nClause.",
                    )
                )
            self.messages.append(
                Message(role="assistant", content=f"reply-{len(received)}")
            )
            return f"reply-{len(received)}"

    monkeypatch.setattr(chat_agent, "AgentService", FakeAgentService)
    def fake_input(prompt: str) -> str:
        input_prompts.append(prompt)
        return next(inputs)

    monkeypatch.setattr("builtins.input", fake_input)

    chat_agent.main()

    assert received == ["first message", "follow-up"]
    assert input_prompts == [
        f"{chat_agent.GREEN}You:{chat_agent.RESET} ",
        f"{chat_agent.GREEN}You:{chat_agent.RESET} ",
        f"{chat_agent.GREEN}You:{chat_agent.RESET} ",
    ]
    assert capsys.readouterr().out.splitlines() == [
        "Chat with the security compliance Agent. Type exit or quit to stop.",
        f"{chat_agent.BLUE}Agent:{chat_agent.RESET} reply-1",
        (
            f"{chat_agent.YELLOW}System:{chat_agent.RESET} "
            "Regulation search: follow-up"
        ),
        "Search results:",
        "Clause.",
        f"{chat_agent.BLUE}Agent:{chat_agent.RESET} reply-2",
    ]
