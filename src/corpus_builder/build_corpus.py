"""Build the shared regulation corpus from all registered PDF handlers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeAlias

from api import embedded_api
from corpus_builder import handle_s17, vector_store
from corpus_builder.models import CorpusRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]
S17_PDF_PATH = PROJECT_ROOT / "data/raw/standards/en/S17_EN_v8.2_2025-04.pdf"

CorpusHandler: TypeAlias = Callable[[], list[CorpusRecord]]


def _build_s17_records() -> list[CorpusRecord]:
    """Run the S17 handler with the project's configured source PDF."""
    return handle_s17.handle_s17(S17_PDF_PATH)


# Add each future regulation handler here.  Every handler must only return records.
HANDLERS: tuple[CorpusHandler, ...] = (_build_s17_records,)


def build_corpus(handlers: Sequence[CorpusHandler] | None = None) -> list[CorpusRecord]:
    """Collect all records, embed them, and write them to the shared vector store."""
    active_handlers = HANDLERS if handlers is None else handlers
    records = [record for handler in active_handlers for record in handler()]
    _validate_records(records)

    vectors = embedded_api.embed_texts([record.text for record in records])
    vector_store.store_vectors(records, vectors)
    return records


def _validate_records(records: Sequence[CorpusRecord]) -> None:
    """Reject an empty corpus or duplicate IDs before any external work begins."""
    if not records:
        raise ValueError("Corpus build received no records from its handlers.")

    duplicate_counts = Counter(record.id for record in records)
    duplicates = sorted(record_id for record_id, count in duplicate_counts.items() if count > 1)
    if duplicates:
        raise ValueError(f"Corpus build received duplicate record IDs: {duplicates}")


def main() -> None:
    """Build the shared corpus using the registered regulation handlers."""
    records = build_corpus()
    print(f"Stored {len(records)} records in the shared vector database.")


if __name__ == "__main__":
    main()
