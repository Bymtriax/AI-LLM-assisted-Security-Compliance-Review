"""Extract section-aware chunks from the English S17 PDF for RAG experiments."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PDF = PROJECT_ROOT / "data/raw/standards/en/S17_EN_v8.2_2025-04.pdf"
EXPERIMENT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_JSONL = EXPERIMENT_OUTPUT_DIR / "s17_en_chunks.jsonl"
REVIEW_MARKDOWN = EXPERIMENT_OUTPUT_DIR / "s17_en_chunks_review.md"
REPORT_JSON = EXPERIMENT_OUTPUT_DIR / "s17_en_chunk_report.json"

DOCUMENT = "S17"
VERSION = "8.2"

TOP_SECTION_RE = re.compile(r"^(\d+)\.\s+([A-Z][A-Z &,/\-]+)$")
SUBSECTION_RE = re.compile(r"^(\d+\.\d+)\.\s+(.+)$")
CONTROL_RE = re.compile(r"^(\d+\.\d+\.\d+)\.\s+(.+)$")
PAGE_LABEL_RE = re.compile(r"^Ref\. No\.\s*:\s*S17\s+(.+)$")


@dataclass
class ActiveChunk:
    kind: str
    section: str
    parent_titles: list[str]
    pdf_page_start: int
    printed_page_start: str | None
    lines: list[str] = field(default_factory=list)


def normalise_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def extract_page_lines(page_text: str) -> tuple[list[str], str | None]:
    """Remove known S17 page chrome while preserving the body text."""
    lines: list[str] = []
    printed_page: str | None = None

    for raw_line in page_text.splitlines():
        line = normalise_line(raw_line)
        if not line:
            continue
        if line.startswith("BASELINE IT SECURITY POLICY"):
            continue

        page_match = PAGE_LABEL_RE.match(line)
        if page_match:
            printed_page = page_match.group(1).strip()
            continue

        lines.append(line)

    return lines, printed_page


def make_chunk(active: ActiveChunk, counters: Counter[str]) -> dict[str, object] | None:
    body = " ".join(active.lines).strip()
    if not body:
        return None

    suffix = "overview" if active.kind == "overview" else "clause"
    base_id = f"{DOCUMENT}-v{VERSION}-{active.section}-{suffix}"
    counters[base_id] += 1
    chunk_id = base_id if counters[base_id] == 1 else f"{base_id}-{counters[base_id]}"

    return {
        "id": chunk_id,
        "document": DOCUMENT,
        "version": VERSION,
        "language": "en",
        "section": active.section,
        "kind": active.kind,
        "parent_titles": active.parent_titles,
        "pdf_page_start": active.pdf_page_start,
        "printed_page_start": active.printed_page_start,
        "text": body,
        "source_file": str(SOURCE_PDF.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }


def build_chunks(pdf_path: Path) -> tuple[list[dict[str, object]], int]:
    reader = PdfReader(str(pdf_path))
    chunks: list[dict[str, object]] = []
    id_counters: Counter[str] = Counter()

    current_top: tuple[str, str] | None = None
    current_sub: tuple[str, str] | None = None
    active: ActiveChunk | None = None

    def flush_active() -> None:
        nonlocal active
        if active is not None:
            chunk = make_chunk(active, id_counters)
            if chunk is not None:
                chunks.append(chunk)
        active = None

    def parent_titles() -> list[str]:
        titles: list[str] = []
        if current_top:
            titles.append(f"{current_top[0]}. {current_top[1]}")
        if current_sub:
            titles.append(f"{current_sub[0]}. {current_sub[1]}")
        return titles

    # Physical pages 1-6 are cover, copyright, amendment history, and contents.
    # The S17 body begins at physical PDF page 7 (printed page 1).
    for pdf_page, page in enumerate(reader.pages, start=1):
        if pdf_page < 7:
            continue

        lines, printed_page = extract_page_lines(page.extract_text() or "")
        for line in lines:
            top_match = TOP_SECTION_RE.match(line)
            if top_match:
                flush_active()
                current_top = (top_match.group(1), top_match.group(2).strip())
                current_sub = None
                continue

            # Check a control before a subsection: 7.1.1 also matches the looser
            # subsection expression if evaluated first.
            control_match = CONTROL_RE.match(line)
            if control_match:
                flush_active()
                active = ActiveChunk(
                    kind="numbered_clause",
                    section=control_match.group(1),
                    parent_titles=parent_titles(),
                    pdf_page_start=pdf_page,
                    printed_page_start=printed_page,
                    lines=[control_match.group(2).strip()],
                )
                continue

            subsection_match = SUBSECTION_RE.match(line)
            if subsection_match:
                flush_active()
                current_sub = (subsection_match.group(1), subsection_match.group(2).strip())
                continue

            if current_top is None:
                continue

            if active is None:
                overview_section = current_sub[0] if current_sub else current_top[0]
                active = ActiveChunk(
                    kind="overview",
                    section=overview_section,
                    parent_titles=parent_titles(),
                    pdf_page_start=pdf_page,
                    printed_page_start=printed_page,
                )
            active.lines.append(line)

    flush_active()
    return chunks, len(reader.pages)


def text_hash(text: str) -> str:
    """Return a stable fingerprint so a reviewer can verify the exact text."""
    return sha256(text.encode("utf-8")).hexdigest()


def render_review_markdown(chunks: list[dict[str, object]]) -> str:
    """Render the same chunk data as a readable, non-editable review view."""
    lines = [
        "# S17 English Chunk Review",
        "",
        "> This file is generated from `s17_en_chunks.jsonl`. Do not edit it; rerun the script instead.",
        "",
        f"- Total chunks: **{len(chunks)}**",
        f"- Source: `{chunks[0]['source_file'] if chunks else SOURCE_PDF.name}`",
        "",
        "---",
    ]

    for index, chunk in enumerate(chunks, start=1):
        parent_titles = " → ".join(chunk["parent_titles"]) or "—"
        body = str(chunk["text"])
        lines.extend(
            [
                "",
                f"## {index}. `{chunk['id']}`",
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| Type | {chunk['kind']} |",
                f"| Section | {chunk['section']} |",
                f"| Parent titles | {parent_titles} |",
                f"| PDF page | {chunk['pdf_page_start']} |",
                f"| Printed page | {chunk['printed_page_start'] or '—'} |",
                f"| Text SHA-256 | `{text_hash(body)}` |",
                "",
                "**Text**",
                "",
                body,
                "",
                "---",
            ]
        )

    return "\n".join(lines) + "\n"


def validate_outputs(chunks: list[dict[str, object]]) -> None:
    """Fail fast unless the JSONL and review view exactly represent the same chunks."""
    jsonl_chunks = [
        json.loads(line)
        for line in OUTPUT_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if jsonl_chunks != chunks:
        raise ValueError("Validation failed: JSONL records differ from the generated chunks.")

    actual_review = REVIEW_MARKDOWN.read_text(encoding="utf-8")
    expected_review = render_review_markdown(jsonl_chunks)
    if actual_review != expected_review:
        raise ValueError("Validation failed: review Markdown does not exactly match the JSONL records.")

    jsonl_text_hashes = [text_hash(str(chunk["text"])) for chunk in jsonl_chunks]
    chunk_text_hashes = [text_hash(str(chunk["text"])) for chunk in chunks]
    if jsonl_text_hashes != chunk_text_hashes:
        raise ValueError("Validation failed: JSONL text hashes differ from the generated chunks.")


def main() -> None:
    if not SOURCE_PDF.exists():
        raise FileNotFoundError(f"S17 source PDF not found: {SOURCE_PDF}")

    chunks, page_count = build_chunks(SOURCE_PDF)
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_JSONL.open("w", encoding="utf-8") as output_file:
        for chunk in chunks:
            output_file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    REVIEW_MARKDOWN.write_text(render_review_markdown(chunks), encoding="utf-8")
    validate_outputs(chunks)

    report = {
        "source_file": str(SOURCE_PDF.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "page_count": page_count,
        "chunk_count": len(chunks),
        "numbered_clause_count": sum(chunk["kind"] == "numbered_clause" for chunk in chunks),
        "overview_chunk_count": sum(chunk["kind"] == "overview" for chunk in chunks),
        "output_file": str(OUTPUT_JSONL.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "review_output_file": str(REVIEW_MARKDOWN.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "validation": "passed",
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print("\nFirst five chunks:")
    for chunk in chunks[:5]:
        print(f"- {chunk['id']}: {chunk['text'][:180]}")


if __name__ == "__main__":
    main()
