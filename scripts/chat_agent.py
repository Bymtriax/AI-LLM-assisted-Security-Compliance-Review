"""Chat with the Agent in the terminal."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import AgentService


GREEN = "\033[32m"
BLUE = "\033[34m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def main() -> None:
    agent = AgentService()
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

        previous_message_count = len(agent.messages)
        try:
            answer = agent.respond(text)
        except Exception as error:
            print(f"Error: {error}")
        else:
            for message in agent.messages[previous_message_count:]:
                if message.role == "system":
                    print(f"{YELLOW}System:{RESET} {message.content}")
            print(f"{BLUE}Agent:{RESET} {answer}")


if __name__ == "__main__":
    main()
