"""Split the English S17/G3 PDFs into JSON under data/processed."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder.split_pdf import main


if __name__ == "__main__":
    main()
