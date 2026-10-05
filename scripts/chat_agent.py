"""Chat with the Agent in the terminal."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import AgentService, ModelResponseError
from api import Message


GREEN = "\033[32m"
BLUE = "\033[34m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def main() -> None:
    agent = AgentService()
    messages: list[Message] = []
    print("Chat with the security compliance Agent. Type exit or quit to stop.")

    while True:
        try:
            text = input(f"{GREEN}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if text.lower() in {"exit", "quit"}:
            break
        if not text:
            continue

        current_messages = [*messages, Message(role="user", content=text)]
        try:
            replies = agent.respond(current_messages)
        except Exception as error:
            print(f"Error: {error}")
            if isinstance(error, ModelResponseError):
                print(f"Raw model reply: {error.raw_response!r}")
        else:
            messages = [
                *current_messages,
                *(message for message in replies if message.role == "assistant"),
            ]
            for message in replies:
                if message.role == "system":
                    print(f"{YELLOW}System: {message.content}{RESET}")
                else:
                    print(f"{BLUE}Agent:{RESET} {message.content}")


if __name__ == "__main__":
    main()
