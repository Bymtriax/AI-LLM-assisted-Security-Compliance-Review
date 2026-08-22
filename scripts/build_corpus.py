"""Run the shared regulation-corpus build from the repository root."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder.build_corpus import main


if __name__ == "__main__":
    main()
