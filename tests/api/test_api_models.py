"""Tests for external API data types."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api import Message


def test_message_stores_role_and_content() -> None:
    message = Message(role="user", content="Hello")

    assert message.role == "user"
    assert message.content == "Hello"
