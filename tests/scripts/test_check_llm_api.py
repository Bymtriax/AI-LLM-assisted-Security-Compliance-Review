"""Offline test for the one-shot language-model check script."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts/check_llm_api.py"
SPEC = importlib.util.spec_from_file_location("check_llm_api", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
check_llm_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_llm_api)


def test_main_sends_one_input_and_prints_reply(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: list[str] = []
    monkeypatch.setattr("builtins.input", lambda prompt: "Hello AI")
    monkeypatch.setattr(
        check_llm_api,
        "generate_text",
        lambda text: received.append(text) or "Hello user",
    )

    check_llm_api.main()

    assert received == ["Hello AI"]
    assert "Output: Hello user" in capsys.readouterr().out
