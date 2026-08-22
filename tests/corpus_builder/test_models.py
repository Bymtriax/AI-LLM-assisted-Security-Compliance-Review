"""Tests for the shared corpus record model."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder.models import CorpusRecord


def metadata(**extra: str | int | float | bool) -> dict[str, str | int | float | bool]:
    return {
        "document": "S17",
        "version": "8.2",
        "language": "en",
        "section": "18.1.5",
        "parent_titles": "18. SECURITY INCIDENT MANAGEMENT > 18.1. Management",
        "source_file": "S17.pdf",
        "pdf_page_start": 42,
        "printed_page_start": "36",
        **extra,
    }


def retrieval_text(body: str, section: str = "18.1.5", parent_titles: str | None = None) -> str:
    parent_titles = parent_titles or "18. SECURITY INCIDENT MANAGEMENT > 18.1. Management"
    return f"Section: {section}\nParent sections: {parent_titles}\nText: {body}"


def test_record_preserves_core_data_and_metadata() -> None:
    text = retrieval_text("Security incidents shall be reported immediately.")
    record = CorpusRecord(
        id="s17-18.1.5",
        text=text,
        metadata=metadata(),
    )

    assert record.id == "s17-18.1.5"
    assert record.text == text
    assert dict(record.metadata) == {
        "document": "S17",
        "section": "18.1.5",
        "parent_titles": "18. SECURITY INCIDENT MANAGEMENT > 18.1. Management",
        "source_file": "S17.pdf",
        "printed_page_start": "36",
        "version": "8.2",
        "language": "en",
        "pdf_page_start": 42,
    }


def test_record_metadata_is_read_only_and_cannot_duplicate_reserved_fields() -> None:
    source_metadata = metadata(section="1", parent_titles="1. PURPOSE")
    record = CorpusRecord(
        id="s17-1",
        text=retrieval_text("Purpose.", section="1", parent_titles="1. PURPOSE"),
        metadata=source_metadata,
    )

    with pytest.raises(TypeError):
        record.metadata["document"] = "G3"  # type: ignore[index]
    source_metadata["document"] = "G3"
    assert record.metadata["document"] == "S17"
    with pytest.raises(ValueError, match="duplicate reserved fields"):
        CorpusRecord("s17-1", "Purpose.", metadata(id="s17-1"))


@pytest.mark.parametrize(
    "missing_key",
    (
        "document",
        "version",
        "language",
        "section",
        "parent_titles",
        "source_file",
        "pdf_page_start",
        "printed_page_start",
    ),
)
def test_record_rejects_each_missing_required_metadata_field(missing_key: str) -> None:
    incomplete = metadata()
    del incomplete[missing_key]

    with pytest.raises(ValueError, match="missing required fields"):
        CorpusRecord("s17-1", "Purpose.", incomplete)


@pytest.mark.parametrize("field", ("document", "version", "language", "section", "parent_titles", "source_file"))
def test_record_rejects_empty_required_text_metadata(field: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        CorpusRecord("s17-1", "Purpose.", metadata(**{field: "  "}))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("pdf_page_start", "42", "must be int"),
        ("pdf_page_start", True, "must be int"),
        ("pdf_page_start", 0, "must be positive"),
        ("pdf_page_start", -1, "must be positive"),
        ("section", 18, "must be str"),
    ),
)
def test_record_rejects_invalid_required_metadata_values(
    field: str,
    value: str | int | bool,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CorpusRecord("s17-1", "Purpose.", metadata(**{field: value}))


@pytest.mark.parametrize("invalid_value", (None, ["nested"], {"nested": "value"}))
def test_record_rejects_metadata_values_chroma_cannot_store(invalid_value: object) -> None:
    with pytest.raises(ValueError, match="strings, numbers or booleans"):
        CorpusRecord("s17-1", "Purpose.", metadata(extra=invalid_value))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="pdf_page_start.*must be int"):
        CorpusRecord("s17-1", "Purpose.", metadata(pdf_page_start="42"))
