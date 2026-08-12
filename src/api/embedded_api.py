"""Small wrapper around the SiliconFlow embedding API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_URL = "https://api.siliconflow.cn/v1/embeddings"
MODEL = "Qwen/Qwen3-VL-Embedding-8B"
MAX_BATCH_SIZE = 8


def embed_text(text: str) -> list[float]:
    """Convert one non-empty text into one vector."""
    return embed_texts([text])[0]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convert texts into vectors in the same order as the input texts."""
    if not texts:
        return []
    if any(not text.strip() for text in texts):
        raise ValueError("Embedding input texts cannot be empty.")

    vectors: list[list[float]] = []
    for start in range(0, len(texts), MAX_BATCH_SIZE):
        vectors.extend(_request_vectors(texts[start : start + MAX_BATCH_SIZE]))
    return vectors


def _request_vectors(texts: list[str]) -> list[list[float]]:
    """Call SiliconFlow once. This private helper handles one safe-size batch."""
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        raise RuntimeError("Set SILICONFLOW_API_KEY in the project's .env file.")

    request = Request(
        API_URL,
        data=json.dumps({"model": MODEL, "input": texts}).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))["data"]
    except HTTPError as error:
        raise RuntimeError(f"Embedding API returned HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach embedding API: {error.reason}") from error

    data = sorted(data, key=lambda item: item["index"])
    if [item["index"] for item in data] != list(range(len(texts))):
        raise RuntimeError("Embedding API response indexes do not match the input order.")

    vectors = [item["embedding"] for item in data]
    if len(vectors) != len(texts) or any(not vector for vector in vectors):
        raise RuntimeError("Embedding API returned invalid vectors.")
    return vectors
