"""Offline tests for the standalone English PDF-to-JSON workflow."""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from corpus_builder import split_pdf
from corpus_builder.models import CorpusRecord


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


def fake_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pages: list[str]) -> Path:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    reader = type("FakeReader", (), {"pages": [FakePage(text) for text in pages]})()
    monkeypatch.setattr(split_pdf, "PdfReader", lambda path: reader)
    return pdf_path


@pytest.mark.parametrize("document,version,dot,header", [
    ("S17", "8.2", ".", "BASELINE IT SECURITY POLICY"),
    ("G3", "10.2", "", "IT SECURITY GUIDELINES"),
])
def test_shared_parser_skips_front_matter_and_preserves_traceability(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    document: str, version: str, dot: str, header: str,
) -> None:
    path = fake_pdf(monkeypatch, tmp_path, [
        "Cover",
        f"{header} CONTENTS\nRef. No.: {document} iii-1\n1{dot} PURPOSE\nContents text",
        f"{header} PURPOSE\nRef. No.: {document} 1\n1{dot} PURPOSE\nBody starts here.",
        f"{header} COMMUNICATIONS\nWRAPPED RUNNING HEADER\nRef. No. : {document} 2\n"
        f"15{dot} COMMUNICATIONS SECURITY\n15.2{dot} Information Transfer\n"
        "15.2.2 Classified information shall be encrypted during transmission.",
    ])

    records = split_pdf.split_pdf(path, document=document, version=version)

    assert len(records) == 2
    assert isinstance(records[1], CorpusRecord)
    assert records[1].id == f"{document}-v{version}-15.2.2-clause-part-01"
    assert records[1].metadata["pdf_page_start"] == 4
    assert records[1].metadata["printed_page_start"] == "2"
    assert records[1].metadata["source_file"] == str(path.resolve())
    assert records[1].metadata["parent_titles"] == (
        "15. COMMUNICATIONS SECURITY > 15.2. Information Transfer"
    )
    assert records[1].text.endswith("Text: Classified information shall be encrypted during transmission.")
    assert all("Contents text" not in record.text and "RUNNING HEADER" not in record.text for record in records)
    assert records[1].metadata["text_sha256"] == sha256(records[1].text.encode()).hexdigest()


def test_g3_lettered_headings_and_appendices_stay_in_their_own_sections(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    path = fake_pdf(monkeypatch, tmp_path, [
        "IT SECURITY GUIDELINES PURPOSE\nRef. No.: G3 1\n1 PURPOSE\nGuidance.",
        "IT SECURITY GUIDELINES ACCESS CONTROL\nRef. No.: G3 43\n11. ACCESS CONTROL\n"
        "11.4 System and Application Access Control\n(a) Information Access Restriction\n"
        "Access shall be restricted.\n(b) Password Policy\nPasswords shall be protected.",
        "IT SECURITY GUIDELINES APPENDIX A\nRef. No.: G3 A-1\n"
        "APPENDIX A SAMPLE END USER INSTRUCTIONS\n\nUsers shall follow these instructions.",
        "\n• Unlabelled appendix pages shall be kept.",
        "IT SECURITY GUIDELINES APPENDIX D\nRef. No.: G3 D-1\n"
        "APPENDIX D INFORMATION SECURITY COMPLIANCE\nMONITORING AND AUDIT MECHANISM\n\n"
        "1. B/Ds shall submit their reports.",
    ])

    records = split_pdf.split_pdf(path, document="G3", version="10.2")

    assert [record.metadata["section"] for record in records] == [
        "1", "11.4(a)", "11.4(b)", "APPENDIX-A", "APPENDIX-D",
    ]
    assert "Unlabelled appendix pages shall be kept." in records[3].text
    assert records[-1].metadata["parent_titles"] == (
        "APPENDIX-D. INFORMATION SECURITY COMPLIANCE MONITORING AND AUDIT MECHANISM"
    )
    assert "1. B/Ds shall submit their reports." in records[-1].text


def test_long_text_is_bounded_without_losing_words_and_json_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    body = " ".join(f"word{i}" for i in range(700))
    path = fake_pdf(monkeypatch, tmp_path, [f"Ref. No.: G3 1\n1 PURPOSE\n{body}"])
    records = split_pdf.split_pdf(path, document="G3", version="10.2")
    output = tmp_path / "processed/g3_en_chunks.json"

    split_pdf.write_records_json(records, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert " ".join(record.text.split("\nText: ", 1)[1] for record in records) == body
    assert max(record.metadata["word_count"] for record in records) <= 220
    assert [record.metadata["part_number"] for record in records] == [1, 2, 3, 4]
    assert len({record.metadata["parent_chunk_id"] for record in records}) == 1
    assert {record.metadata["split_method"] for record in records} == {"word_boundary"}
    assert all(record.metadata["part_count"] == 4 for record in records)
    assert [CorpusRecord(**entry) for entry in payload] == records
    assert all(set(entry) == {"id", "text", "metadata"} for entry in payload)


def test_g3_contents_identify_single_word_and_wrapped_headings_without_promoting_nested_lists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    path = fake_pdf(monkeypatch, tmp_path, [
        "IT SECURITY GUIDELINES CONTENTS\nRef. No.: G3 iii-1\n"
        "9.1 NEW, DURING OR TERMINATION OF EMPLOYMENT ..... 30\n"
        "(c) Training ..... 30\n"
        "(f) IT Security Responsibilities after Termination or Change of\nEmployment ..... 33",
        "IT SECURITY GUIDELINES PURPOSE\nRef. No.: G3 1\n1 PURPOSE\nGuidance.",
        "IT SECURITY GUIDELINES HUMAN RESOURCE SECURITY\nRef. No.: G3 30\n"
        "9. HUMAN RESOURCE SECURITY\n9.1 New, During or Termination of Employment\n"
        "(c) Training\n\nTraining shall be provided.\n"
        "(a) Programme objectives\n\nDocument these objectives.\n"
        "(f) IT Security Responsibilities after Termination or Change of\nEmployment\n\n"
        "Access shall be revoked.",
    ])

    records = split_pdf.split_pdf(path, document="G3", version="10.2")

    assert [record.metadata["section"] for record in records] == ["1", "9.1(c)", "9.1(f)"]
    assert "(a) Programme objectives" in records[1].text
    assert "Change of Employment" in records[2].text


def test_main_exports_both_documents_without_embedding_or_storage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    path = fake_pdf(monkeypatch, tmp_path, ["Ref. No.: S17 1\n1. PURPOSE\nBody • preserved."])
    s17 = split_pdf.split_pdf(path, document="S17", version="8.2")
    path = fake_pdf(monkeypatch, tmp_path, ["Ref. No.: G3 1\n1 PURPOSE\nGuidance • preserved."])
    g3 = split_pdf.split_pdf(path, document="G3", version="10.2")
    calls: list[str] = []

    def split(path: Path, *, document: str, version: str) -> list[CorpusRecord]:
        calls.append(document)
        return s17 if document == "S17" else g3

    monkeypatch.setattr(split_pdf, "split_pdf", split)
    split_pdf.main(["--output-dir", str(tmp_path / "processed")])

    assert calls == ["S17", "G3"]
    for document in calls:
        output = tmp_path / "processed" / f"{document.lower()}_en_chunks.json"
        assert json.loads(output.read_text(encoding="utf-8"))[0]["metadata"]["document"] == document
        assert "•" in output.read_text(encoding="utf-8")


def test_g3_uses_body_title_when_contents_differ_and_keeps_wrapped_cross_references(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    path = fake_pdf(monkeypatch, tmp_path, [
        "IT SECURITY GUIDELINES CONTENTS\nRef. No.: G3 iii-1\n"
        "14.6 TECHNICAL VULNERABILITY MANAGEMENT ..... 71\n"
        "(e) Source Code Scanning ..... 73\n"
        "15.2 INFORMATION TRANSFER ..... 91\n(d) Communication with External Parties ..... 94",
        "Ref. No.: G3 1\n1 PURPOSE\nGuidance.",
        "Ref. No.: G3 73\n14. OPERATIONS SECURITY\n14.6 Technical Vulnerability Management\n"
        "(e) Source Code Review\n\nSource code shall be reviewed.",
        "Ref. No.: G3 93\n15. COMMUNICATIONS SECURITY\n15.2 Information Transfer\n"
        "Please refer to Section\n14.2 – Protection from Malware for details.\n"
        "(d) Communication with External Parties\n\nExternal connections shall be secured.",
    ])

    records = split_pdf.split_pdf(path, document="G3", version="10.2")

    assert [record.metadata["section"] for record in records] == ["1", "14.6(e)", "15.2", "15.2(d)"]
    assert "Source Code Review" in records[1].text
    assert "Please refer to Section 14.2 – Protection from Malware for details." in records[2].text


def test_rejects_missing_empty_or_mismatched_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        split_pdf.split_pdf(tmp_path / "missing.pdf", document="G3", version="10.2")
    path = fake_pdf(monkeypatch, tmp_path, ["Cover only"])
    with pytest.raises(ValueError, match="no records"):
        split_pdf.split_pdf(path, document="G3", version="10.2")
    path = fake_pdf(monkeypatch, tmp_path, ["Ref. No.: S17 1\n1. PURPOSE\nBody."])
    with pytest.raises(ValueError, match="reference does not match"):
        split_pdf.split_pdf(path, document="G3", version="10.2")
