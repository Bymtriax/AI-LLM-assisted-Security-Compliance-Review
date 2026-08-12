"""QA tests for the real embedded_api module, without calling SiliconFlow."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api import embedded_api


def test_embed_text_returns_one_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    """The single-text interface delegates to the real batch interface."""
    received: list[list[str]] = []

    def fake_request(texts: list[str]) -> list[list[float]]:
        received.append(texts)
        return [[1.0, 2.0]]

    monkeypatch.setattr(embedded_api, "_request_vectors", fake_request)

    assert embedded_api.embed_text("encryption requirement") == [1.0, 2.0]
    assert received == [["encryption requirement"]]


def test_embed_texts_splits_nine_inputs_into_eight_and_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public batch interface must hide SiliconFlow's 8-item batch limit."""
    received: list[list[str]] = []

    def fake_request(texts: list[str]) -> list[list[float]]:
        received.append(texts)
        return [[float(int(text.removeprefix("text-")))] for text in texts]

    monkeypatch.setattr(embedded_api, "_request_vectors", fake_request)
    texts = [f"text-{number}" for number in range(9)]

    assert embedded_api.embed_texts(texts) == [[float(number)] for number in range(9)]
    assert [len(batch) for batch in received] == [8, 1]


def test_embed_texts_returns_empty_list_without_calling_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No input means no API request and no vectors."""
    monkeypatch.setattr(
        embedded_api,
        "_request_vectors",
        lambda texts: pytest.fail("The API helper must not be called for an empty list."),
    )

    assert embedded_api.embed_texts([]) == []


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_text_is_rejected(text: str) -> None:
    """An empty text must fail before it reaches the API."""
    with pytest.raises(ValueError, match="cannot be empty"):
        embedded_api.embed_text(text)


def test_invalid_api_response_indexes_raise_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The private API helper rejects a response that cannot be mapped to inputs."""
    monkeypatch.setattr(embedded_api, "load_dotenv", lambda path: None)
    monkeypatch.setattr(embedded_api.os, "environ", {"SILICONFLOW_API_KEY": "test-key"})

    class FakeResponse:
        def read(self) -> bytes:
            return b'{"data": [{"index": 1, "embedding": [1.0]}]}'

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(embedded_api, "urlopen", lambda request, timeout: FakeResponse())

    with pytest.raises(RuntimeError, match="indexes do not match"):
        embedded_api._request_vectors(["one text"])
