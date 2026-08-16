"""Tests for extracting vector-store-ready records from an S17 PDF."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder import handle_s17
from api import embedded_api
from corpus_builder import vector_store


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages


def test_handle_s17_returns_vector_store_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One PDF is returned as a list of id/text/metadata records."""
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
    assert set(records[0]) == {"id", "text", "metadata"}
    assert records[0]["id"] == "S17-v8.2-15.2.2-clause-part-01"
    assert records[0]["text"] == (
        "Classified information shall be encrypted during transmission. "
        "Further controls shall protect the transfer from unauthorised access."
    )
    assert records[0]["metadata"]["section"] == "15.2.2"
    assert records[0]["metadata"]["parent_titles"] == (
        "15. COMMUNICATIONS SECURITY > 15.2. Information Transfer"
    )
    assert records[0]["metadata"]["printed_page_start"] == "33"


def test_handle_s17_rejects_a_missing_pdf(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="source PDF not found"):
        handle_s17.handle_s17(tmp_path / "missing.pdf")


def test_validate_records_rejects_duplicate_ids() -> None:
    records = [
        {"id": "same", "text": "First", "metadata": {"word_count": 1}},
        {"id": "same", "text": "Second", "metadata": {"word_count": 1}},
    ]

    with pytest.raises(ValueError, match="duplicate"):
        handle_s17._validate_records(records)


def test_main_embeds_only_text_and_stores_the_original_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata stays in records and is not included in the embedding input."""
    records = [
        {
            "id": "S17-one",
            "text": "The legal text only.",
            "metadata": {"section": "1", "source_file": "S17.pdf"},
        }
    ]
    received: dict[str, object] = {}
    monkeypatch.setattr(handle_s17, "handle_s17", lambda: records)

    def fake_embed(texts: list[str]) -> list[list[float]]:
        received["texts"] = texts
        return [[1.0, 0.0]]

    def fake_store(
        stored_records: list[dict[str, object]],
        vectors: list[list[float]],
    ) -> None:
        received["records"] = stored_records
        received["vectors"] = vectors

    monkeypatch.setattr(embedded_api, "embed_texts", fake_embed)
    monkeypatch.setattr(vector_store, "store_vectors", fake_store)

    handle_s17.main()

    assert received["texts"] == ["The legal text only."]
    assert received["records"] is records
    assert received["vectors"] == [[1.0, 0.0]]
