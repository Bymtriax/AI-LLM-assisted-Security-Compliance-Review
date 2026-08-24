"""Offline test for the SiliconFlow language-model API."""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api import generate_text
from api import llm_api


class FakeResponse:
    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": "AI reply"}}]}
        ).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_generate_text_sends_text_and_returns_reply(monkeypatch: object) -> None:
    received: dict[str, object] = {}
    monkeypatch.setattr(llm_api, "load_dotenv", lambda path: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        llm_api.os,
        "environ",
        {"SILICONFLOW_API_KEY": "test-key"},
    )

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        received["body"] = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        return FakeResponse()

    monkeypatch.setattr(llm_api, "urlopen", fake_urlopen)  # type: ignore[attr-defined]

    assert generate_text("Hello") == "AI reply"
    assert received["body"] == {
        "model": llm_api.MODEL,
        "messages": [{"role": "user", "content": "Hello"}],
    }
