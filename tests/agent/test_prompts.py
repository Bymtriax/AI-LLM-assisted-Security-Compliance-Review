"""Tests for Agent prompts."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent.prompts import SYSTEM_MESSAGE


def test_system_message_describes_context_flow_and_retrieval_tool() -> None:
    assert SYSTEM_MESSAGE.role == "system"
    assert "security compliance assistant" in SYSTEM_MESSAGE.content
    assert "only the English S17 version" in SYSTEM_MESSAGE.content
    assert "It does not yet contain G3" in SYSTEM_MESSAGE.content
    assert "Never claim" in SYSTEM_MESSAGE.content
    assert "unavailable material was retrieved" in SYSTEM_MESSAGE.content
    assert "Decide whether regulatory evidence is needed" in SYSTEM_MESSAGE.content
    assert '"type":"tool_call"' in SYSTEM_MESSAGE.content
    assert '"tool":"retrieve_regulations"' in SYSTEM_MESSAGE.content
    assert '"type":"answer"' in SYSTEM_MESSAGE.content
