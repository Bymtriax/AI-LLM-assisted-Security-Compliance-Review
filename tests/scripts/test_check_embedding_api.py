"""Tests for the one-shot embedding API check script's response validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts/check_embedding_api.py"
SPEC = importlib.util.spec_from_file_location("check_embedding_api", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
check_embedding_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_embedding_api)


def test_embedding_dimension_accepts_one_numeric_embedding() -> None:
    assert check_embedding_api._embedding_dimension(
        {"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]}
    ) == 3


def test_main_sends_the_contextual_record_format(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: dict[str, object] = {}

    class FakeResponse:
        def read(self) -> bytes:
            return b'{"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]}'

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request, timeout: int) -> FakeResponse:
        received["request"] = request
        received["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(check_embedding_api, "load_dotenv", lambda path: None)
    monkeypatch.setattr(check_embedding_api.os, "environ", {"SILICONFLOW_API_KEY": "test-key"})
    monkeypatch.setattr(check_embedding_api, "urlopen", fake_urlopen)

    check_embedding_api.main()

    request = received["request"]
    assert json.loads(request.data.decode("utf-8"))["input"] == check_embedding_api.CHECK_TEXT
    assert received["timeout"] == 30
    assert "vector dimension 3" in capsys.readouterr().out


@pytest.mark.parametrize(
    "payload",
    (
        {},
        {"data": []},
        {"data": [{"index": 1, "embedding": [0.1]}]},
        {"data": [{"index": 0, "embedding": []}]},
        {"data": [{"index": 0, "embedding": ["bad"]}]},
    ),
)
def test_embedding_dimension_rejects_invalid_responses(payload: object) -> None:
    with pytest.raises(ValueError):
        check_embedding_api._embedding_dimension(payload)
