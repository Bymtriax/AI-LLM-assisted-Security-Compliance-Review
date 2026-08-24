"""Manually send one text to the language model."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api import generate_text


def main() -> None:
    text = input("Input: ")
    result = generate_text(text)
    print(f"Output: {result}")


if __name__ == "__main__":
    main()
