"""Tests for extracting vector-store-ready records from an S17 PDF."""

from __future__ import annotations

import sys
from hashlib import sha256
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder import handle_s17
from corpus_builder.models import CorpusRecord


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages


def metadata(**extra: str | int | float | bool) -> dict[str, str | int | float | bool]:
    return {
        "document": "S17",
        "version": "8.2",
        "language": "en",
        "section": "1",
        "parent_titles": "1. PURPOSE",
        "source_file": "S17.pdf",
        "pdf_page_start": 1,
        "printed_page_start": "1",
        **extra,
    }


def retrieval_text(body: str) -> str:
    return f"Section: 1\nParent sections: 1. PURPOSE\nText: {body}"


def test_handle_s17_returns_corpus_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One PDF is returned as a list of typed corpus records."""
    pdf_path = tmp_path / "S17.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    pages = [FakePage("") for _ in range(6)]
    pages.append(
        FakePage(
            "\n".join(
                [
                    "BASELINE IT SECURITY POLICY COMMUNICATIONS SECURITY",
                    "INFORMATION SECURITY",
                    "Ref. No. : S17 33",
                    "15. COMMUNICATIONS SECURITY",
                    "15.2. Information Transfer",
                    "15.2.2 Classified information shall be encrypted during transmission.",
                    "Further controls shall protect the transfer from unauthorised access.",
                ]
            )
        )
    )
    monkeypatch.setattr(handle_s17, "PdfReader", lambda path: FakeReader(pages))

    records = handle_s17.handle_s17(pdf_path)

    assert len(records) == 1
    assert isinstance(records[0], CorpusRecord)
    assert records[0].id == "S17-v8.2-15.2.2-clause-part-01"
    assert records[0].text == (
        "Section: 15.2.2\n"
        "Parent sections: 15. COMMUNICATIONS SECURITY > 15.2. Information Transfer\n"
        "Text: Classified information shall be encrypted during transmission. "
        "Further controls shall protect the transfer from unauthorised access."
    )
    assert records[0].metadata["section"] == "15.2.2"
    assert records[0].metadata["parent_titles"] == (
        "15. COMMUNICATIONS SECURITY > 15.2. Information Transfer"
    )
    assert records[0].metadata["printed_page_start"] == "33"
    assert records[0].metadata["text_sha256"] == sha256(records[0].text.encode("utf-8")).hexdigest()
    assert set(records[0].metadata) == {
        "document",
        "version",
        "language",
        "section",
        "parent_titles",
        "parent_chunk_id",
        "source_kind",
        "split_method",
        "part_number",
        "part_count",
        "pdf_page_start",
        "printed_page_start",
        "word_count",
        "text_sha256",
        "source_file",
    }


def test_handle_s17_rejects_a_missing_pdf(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="source PDF not found"):
        handle_s17.handle_s17(tmp_path / "missing.pdf")


def test_handle_s17_requires_a_pdf_path() -> None:
    with pytest.raises(TypeError, match="pdf_path"):
        handle_s17.handle_s17()  # type: ignore[call-arg]


def test_validate_records_rejects_duplicate_ids() -> None:
    records = [
        CorpusRecord("same", retrieval_text("First"), metadata(word_count=1)),
        CorpusRecord("same", retrieval_text("Second"), metadata(word_count=1)),
    ]

    with pytest.raises(ValueError, match="duplicate"):
        handle_s17._validate_records(records)


def test_build_records_keeps_split_parts_linked_to_one_parent_chunk() -> None:
    first_sentence = " ".join(["First"] * 221) + "."
    second_sentence = " ".join(["Second"] * 221) + "."
    chunk = handle_s17._StructuralChunk(
        id="S17-v8.2-15.2.2-clause",
        kind="numbered_clause",
        section="15.2.2",
        parent_titles=["15. COMMUNICATIONS SECURITY", "15.2. Information Transfer"],
        pdf_page_start=33,
        printed_page_start="27",
        lines=[first_sentence, second_sentence],
        source_file="data/raw/standards/en/S17.pdf",
    )

    records = handle_s17._build_records([chunk])

    assert [record.id for record in records] == [
        "S17-v8.2-15.2.2-clause-part-01",
        "S17-v8.2-15.2.2-clause-part-02",
    ]
    assert [record.metadata["parent_chunk_id"] for record in records] == [chunk.id, chunk.id]
    assert [record.metadata["part_number"] for record in records] == [1, 2]
    assert [record.metadata["part_count"] for record in records] == [2, 2]
    assert [record.metadata["split_method"] for record in records] == [
        "sentence_boundary",
        "sentence_boundary",
    ]
    assert [record.text for record in records] == [
        (
            "Section: 15.2.2\n"
            "Parent sections: 15. COMMUNICATIONS SECURITY > 15.2. Information Transfer\n"
            f"Text: {first_sentence}"
        ),
        (
            "Section: 15.2.2\n"
            "Parent sections: 15. COMMUNICATIONS SECURITY > 15.2. Information Transfer\n"
            f"Text: {second_sentence}"
        ),
    ]
