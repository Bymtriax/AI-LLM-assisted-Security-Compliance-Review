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


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        raise SystemExit("Set SILICONFLOW_API_KEY in the project's .env file before running this script.")

    request = Request(
        API_URL,
        data=json.dumps({"input": "Hello, world!", "model": MODEL}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            print(response.read().decode("utf-8"))
    except HTTPError as error:
        raise SystemExit(f"Embedding API returned HTTP {error.code}.") from error
    except URLError as error:
        raise SystemExit(f"Could not reach embedding API: {error.reason}") from error


if __name__ == "__main__":
    main()
