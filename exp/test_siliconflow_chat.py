"""One-time real SiliconFlow DeepSeek-V4-Flash connectivity experiment."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api.llm_api import MODEL, generate_text


TEST_PROMPT = (
    "A project stores confidential data in plaintext. "
    "State one compliance concern in one sentence."
)


def main() -> None:
    """Send one real request and display the returned assistant text."""
    print(f"Model: {MODEL}")
    print("Response:")
    print(generate_text(TEST_PROMPT))


if __name__ == "__main__":
    main()
