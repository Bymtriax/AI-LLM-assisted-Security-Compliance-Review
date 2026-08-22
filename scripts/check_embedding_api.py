"""Manually verify that the configured embedding API is reachable."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


API_URL = "https://api.siliconflow.cn/v1/embeddings"
MODEL = "Qwen/Qwen3-VL-Embedding-8B"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_TEXT = "\n".join(
    [
        "Section: 15.2.2",
        "Parent sections: 15. COMMUNICATIONS SECURITY > 15.2. Information Transfer",
        "Text: Classified information shall be encrypted during transmission.",
    ]
)


def _embedding_dimension(payload: object) -> int:
    """Validate the one-record response and return its vector dimension."""
    if not isinstance(payload, dict):
        raise ValueError("Embedding API returned a non-object JSON response.")
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ValueError("Embedding API did not return exactly one embedding result.")
    if data[0].get("index") != 0:
        raise ValueError("Embedding API response index does not match the one input text.")
    embedding = data[0].get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise ValueError("Embedding API returned an empty or invalid embedding.")
    if any(not isinstance(value, (int, float)) for value in embedding):
        raise ValueError("Embedding API returned a non-numeric embedding value.")
    return len(embedding)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        raise SystemExit("Set SILICONFLOW_API_KEY in the project's .env file before running this script.")

    request = Request(
        API_URL,
        data=json.dumps({"input": CHECK_TEXT, "model": MODEL}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise SystemExit(f"Embedding API returned HTTP {error.code}.") from error
    except URLError as error:
        raise SystemExit(f"Could not reach embedding API: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise SystemExit("Embedding API returned invalid JSON.") from error

    try:
        dimension = _embedding_dimension(payload)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"Embedding API check passed: model {MODEL}; vector dimension {dimension}.")


if __name__ == "__main__":
    main()
