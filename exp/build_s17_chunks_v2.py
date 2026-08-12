"""Build auditable, retrieval-sized chunks from the English S17 PDF.

V1 proved that the PDF structure can be extracted.  This V2 experiment keeps
that structure, but further separates long lists, glossary entries and internal
headings into smaller, focused chunks for later embedding.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PDF = PROJECT_ROOT / "data/raw/standards/en/S17_EN_v8.2_2025-04.pdf"
EXPERIMENT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_JSONL = EXPERIMENT_OUTPUT_DIR / "s17_en_retrieval_chunks_v2.jsonl"
REVIEW_MARKDOWN = EXPERIMENT_OUTPUT_DIR / "s17_en_retrieval_chunks_v2_review.md"
REPORT_JSON = EXPERIMENT_OUTPUT_DIR / "s17_en_retrieval_chunks_v2_report.json"

DOCUMENT = "S17"
VERSION = "8.2"

# These are word-based experiment limits.  We will replace them with the final
# embedding model's tokenizer limits after choosing the embedding model.
TARGET_WORDS = 220
HARD_MAX_WORDS = 300

TOP_SECTION_RE = re.compile(r"^(\d+)\.\s+([A-Z][A-Z &,/\-]+)$")
SUBSECTION_RE = re.compile(r"^(\d+\.\d+)\.\s+(.+)$")
# Some S17 headings have a final full stop (7.1.1.), while others do not (7.2.1).
CONTROL_RE = re.compile(r"^(\d+\.\d+\.\d+)\.?\s+(.+)$")
PAGE_LABEL_RE = re.compile(r"^Ref\. No\.\s*:\s*S17\s+(.+)$")
ENUMERATED_ITEM_RE = re.compile(r"^[a-z]\)\s+", re.IGNORECASE)
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

# Different pages expose the same bullet glyph either as U+2022 or a private-use
# character. Treat both forms as the same structural marker.
PDF_BULLETS = ("\uf09f", "\u2022")
PDF_BULLET_RE = re.compile(r"[\uf09f\u2022]")
DISPLAY_BULLET = "•"
TITLE_CONNECTORS = {"and", "of", "the", "in", "for", "to", "on", "with", "by", "&"}


@dataclass
class ActiveChunk:
    kind: str
    section: str
    parent_titles: list[str]
    pdf_page_start: int
    printed_page_start: str | None
    lines: list[str | None] = field(default_factory=list)


@dataclass
class StructuralChunk:
    """A complete chunk based solely on the document's numbered structure."""

    id: str
    document: str
    version: str
    language: str
    section: str
    kind: str
    parent_titles: list[str]
    pdf_page_start: int
    printed_page_start: str | None
    lines: list[str | None]
    source_file: str

    @property
    def text(self) -> str:
        return clean_text(join_lines(self.lines))


@dataclass
class SemanticUnit:
    text: str
    kind: str


@dataclass
class RetrievalPiece:
    text: str
    split_method: str


def normalise_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def clean_text(text: str) -> str:
    """Make PDF bullet glyphs readable without changing the legal wording."""
    for bullet in PDF_BULLETS:
        text = text.replace(bullet, DISPLAY_BULLET)
    return re.sub(r"\s+", " ", text).strip()


def canonical_text(text: str) -> str:
    """Whitespace-insensitive representation used for coverage validation."""
    return clean_text(text)


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:[/-][A-Za-z0-9]+)*", text))


def text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def extract_page_lines(page_text: str) -> tuple[list[str | None], str | None]:
    """Remove recurring page chrome and retain paragraph boundaries as None."""
    lines: list[str | None] = []
    printed_page: str | None = None
    pending_blank = False

    for raw_line in page_text.splitlines():
        line = normalise_line(raw_line)
        if not line:
            pending_blank = bool(lines)
            continue
        if line.startswith("BASELINE IT SECURITY POLICY"):
            continue

        page_match = PAGE_LABEL_RE.match(line)
        if page_match:
            printed_page = page_match.group(1).strip()
            continue

        if pending_blank and lines and lines[-1] is not None:
            lines.append(None)
        pending_blank = False
        lines.append(line)

    return lines, printed_page


def join_lines(lines: list[str | None]) -> str:
    """Join PDF wrapping while keeping a paragraph separator where available."""
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line is None:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def make_structural_chunk(active: ActiveChunk, counters: Counter[str]) -> StructuralChunk | None:
    if not clean_text(join_lines(active.lines)):
        return None

    suffix = "overview" if active.kind == "overview" else "clause"
    base_id = f"{DOCUMENT}-v{VERSION}-{active.section}-{suffix}"
    counters[base_id] += 1
    chunk_id = base_id if counters[base_id] == 1 else f"{base_id}-{counters[base_id]}"

    return StructuralChunk(
        id=chunk_id,
        document=DOCUMENT,
        version=VERSION,
        language="en",
        section=active.section,
        kind=active.kind,
        parent_titles=active.parent_titles,
        pdf_page_start=active.pdf_page_start,
        printed_page_start=active.printed_page_start,
        lines=active.lines.copy(),
        source_file=str(SOURCE_PDF.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    )


def build_structural_chunks(pdf_path: Path) -> tuple[list[StructuralChunk], int]:
    """Extract complete numbered sections before applying any size-based split."""
    reader = PdfReader(str(pdf_path))
    chunks: list[StructuralChunk] = []
    id_counters: Counter[str] = Counter()

    current_top: tuple[str, str] | None = None
    current_sub: tuple[str, str] | None = None
    active: ActiveChunk | None = None

    def flush_active() -> None:
        nonlocal active
        if active is not None:
            chunk = make_structural_chunk(active, id_counters)
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
    for pdf_page, page in enumerate(reader.pages, start=1):
        if pdf_page < 7:
            continue

        lines, printed_page = extract_page_lines(page.extract_text() or "")
        for line in lines:
            if line is None:
                if active is not None and active.lines and active.lines[-1] is not None:
                    active.lines.append(None)
                continue

            top_match = TOP_SECTION_RE.match(line)
            if top_match:
                flush_active()
                current_top = (top_match.group(1), top_match.group(2).strip())
                current_sub = None
                continue

            # Evaluate the most specific pattern first: 7.1.1 also fits the
            # looser subsection pattern.
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


def is_parenthetical_code(line: str) -> bool:
    return bool(re.fullmatch(r"\([A-Za-z0-9./-]+\)", line))


def is_title_line(line: str) -> bool:
    """Detect a short Title Case subheading preserved on its own PDF line."""
    candidate = PDF_BULLET_RE.sub("", line).strip()
    if not candidate or any(mark in candidate for mark in {".", ";", ":", ","}):
        return False
    if "http" in candidate.lower() or len(candidate) > 90:
        return False

    tokens = re.findall(r"[A-Za-z]+", candidate)
    if not 2 <= len(tokens) <= 12:
        return False
    if any(token.lower() in {"shall", "should", "must", "will"} for token in tokens):
        return False

    title_like = sum(token[0].isupper() or token.isupper() or token.lower() in TITLE_CONNECTORS for token in tokens)
    return title_like / len(tokens) >= 0.8


def build_semantic_units(lines: list[str | None]) -> list[SemanticUnit]:
    """Turn paragraphs, bullets, enumerations and internal headings into units."""
    units: list[SemanticUnit] = []
    current: list[str] = []
    current_kind = "paragraph"

    def flush_current() -> None:
        nonlocal current
        text = clean_text(" ".join(current))
        if text:
            units.append(SemanticUnit(text=text, kind=current_kind))
        current = []

    index = 0
    while index < len(lines):
        line = lines[index]
        if line is None:
            flush_current()
            current_kind = "paragraph"
            index += 1
            continue

        if PDF_BULLET_RE.search(line):
            fragments = PDF_BULLET_RE.split(line)
            before_bullet = fragments[0].strip()
            if before_bullet:
                current.append(before_bullet)
            flush_current()
            for fragment in fragments[1:]:
                if not fragment.strip():
                    continue
                # A new bullet ends the preceding bullet item.  Keep the last
                # one open so its wrapped PDF lines remain part of this item.
                if current:
                    flush_current()
                current_kind = "bullet_item"
                current = [DISPLAY_BULLET, fragment.strip()]
            index += 1
            continue

        if ENUMERATED_ITEM_RE.match(line):
            flush_current()
            current_kind = "enumerated_item"
            current = [line]
            index += 1
            continue

        if is_title_line(line):
            flush_current()
            current_kind = "internal_heading"
            current = [line]
            # Table labels such as "Baseline IT Security Policy" and "(S17)"
            # occupy two lines in the PDF but form one logical heading.
            if index + 1 < len(lines) and lines[index + 1] is not None and is_parenthetical_code(lines[index + 1] or ""):
                current.append(lines[index + 1] or "")
                index += 1
            index += 1
            continue

        current.append(line)
        index += 1

    flush_current()
    return units


def split_to_target(text: str, split_method: str) -> list[RetrievalPiece]:
    """Split only between sentences when a semantic unit remains too long."""
    text = clean_text(text)
    if word_count(text) <= TARGET_WORDS:
        return [RetrievalPiece(text=text, split_method=split_method)]

    sentences = [sentence.strip() for sentence in SENTENCE_BOUNDARY_RE.split(text) if sentence.strip()]
    if len(sentences) <= 1:
        # Keep one indivisible sentence intact and flag it in the report instead
        # of silently breaking a legal statement mid-sentence.
        return [RetrievalPiece(text=text, split_method=f"{split_method}_needs_review")]

    pieces: list[RetrievalPiece] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = clean_text(" ".join([*current, sentence]))
        if current and word_count(candidate) > TARGET_WORDS:
            pieces.append(RetrievalPiece(text=clean_text(" ".join(current)), split_method="sentence_boundary"))
            current = [sentence]
        else:
            current.append(sentence)
    if current:
        pieces.append(RetrievalPiece(text=clean_text(" ".join(current)), split_method="sentence_boundary"))
    return pieces


def make_retrieval_pieces(chunk: StructuralChunk) -> list[RetrievalPiece]:
    """Apply semantic splitting only where the structural chunk is too long."""
    if word_count(chunk.text) <= TARGET_WORDS:
        return [RetrievalPiece(text=chunk.text, split_method="unchanged")]

    units = build_semantic_units(chunk.lines)
    if not units:
        return split_to_target(chunk.text, "sentence_boundary")

    # A clause title often occupies its own PDF line, followed by a blank line.
    # Keep that title with the opening content instead of creating a useless
    # five-word vector such as "Departmental IT Security Officer (DITSO)".
    if (
        len(units) > 1
        and units[0].kind == "internal_heading"
        and word_count(units[0].text) <= 12
    ):
        units[1] = SemanticUnit(
            text=clean_text(f"{units[0].text} {units[1].text}"),
            kind=units[1].kind,
        )
        units = units[1:]

    pieces: list[RetrievalPiece] = []
    paragraph_buffer: list[str] = []

    def flush_paragraph_buffer() -> None:
        nonlocal paragraph_buffer
        if paragraph_buffer:
            pieces.extend(split_to_target(" ".join(paragraph_buffer), "paragraph_group"))
        paragraph_buffer = []

    for unit in units:
        if unit.kind == "paragraph":
            candidate = clean_text(" ".join([*paragraph_buffer, unit.text]))
            if paragraph_buffer and word_count(candidate) > TARGET_WORDS:
                flush_paragraph_buffer()
            paragraph_buffer.append(unit.text)
            continue

        flush_paragraph_buffer()
        pieces.extend(split_to_target(unit.text, unit.kind))

    flush_paragraph_buffer()
    return pieces


def retrieval_record(parent: StructuralChunk, piece: RetrievalPiece, part_number: int, part_count: int) -> dict[str, object]:
    part_suffix = f"part-{part_number:02d}"
    return {
        "id": f"{parent.id}-{part_suffix}",
        "parent_chunk_id": parent.id,
        "document": parent.document,
        "version": parent.version,
        "language": parent.language,
        "section": parent.section,
        "source_kind": parent.kind,
        "split_method": piece.split_method,
        "part_number": part_number,
        "part_count": part_count,
        "parent_titles": parent.parent_titles,
        "pdf_page_start": parent.pdf_page_start,
        "printed_page_start": parent.printed_page_start,
        "word_count": word_count(piece.text),
        "text_sha256": text_hash(piece.text),
        "text": piece.text,
        "source_file": parent.source_file,
    }


def build_retrieval_chunks(structural_chunks: list[StructuralChunk]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for parent in structural_chunks:
        pieces = make_retrieval_pieces(parent)
        for part_number, piece in enumerate(pieces, start=1):
            records.append(retrieval_record(parent, piece, part_number, len(pieces)))
    return records


def render_review_markdown(records: list[dict[str, object]], structural_count: int) -> str:
    """Create an easy-to-read view from the exact records written to JSONL."""
    lines = [
        "# S17 English Retrieval Chunk Review — V2",
        "",
        "> This file is generated from `s17_en_retrieval_chunks_v2.jsonl`. Do not edit it; rerun the experiment script instead.",
        "",
        f"- Structural chunks before semantic splitting: **{structural_count}**",
        f"- Retrieval chunks after semantic splitting: **{len(records)}**",
        f"- Target size: **{TARGET_WORDS} words**; hard review limit: **{HARD_MAX_WORDS} words**",
        f"- Source: `{records[0]['source_file'] if records else SOURCE_PDF.name}`",
        "",
        "---",
    ]

    for index, record in enumerate(records, start=1):
        parent_titles = " → ".join(record["parent_titles"]) or "—"
        lines.extend(
            [
                "",
                f"## {index}. `{record['id']}`",
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| Parent structural chunk | `{record['parent_chunk_id']}` |",
                f"| Section | {record['section']} |",
                f"| Source type | {record['source_kind']} |",
                f"| Split method | {record['split_method']} |",
                f"| Part | {record['part_number']} / {record['part_count']} |",
                f"| Parent titles | {parent_titles} |",
                f"| PDF page | {record['pdf_page_start']} |",
                f"| Printed page | {record['printed_page_start'] or '—'} |",
                f"| Word count | {record['word_count']} |",
                f"| Text SHA-256 | `{record['text_sha256']}` |",
                "",
                "**Text**",
                "",
                str(record["text"]),
                "",
                "---",
            ]
        )

    return "\n".join(lines) + "\n"


def validate_outputs(structural_chunks: list[StructuralChunk], records: list[dict[str, object]]) -> dict[str, int]:
    """Verify IDs, source inheritance, content coverage, length and review fidelity."""
    jsonl_records = [
        json.loads(line)
        for line in OUTPUT_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if jsonl_records != records:
        raise ValueError("Validation failed: JSONL records differ from the generated retrieval chunks.")

    record_ids = [str(record["id"]) for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("Validation failed: duplicate retrieval chunk IDs.")

    by_parent: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        by_parent[str(record["parent_chunk_id"])].append(record)

    for parent in structural_chunks:
        children = by_parent.get(parent.id, [])
        if not children:
            raise ValueError(f"Validation failed: {parent.id} has no retrieval chunks.")
        if any(record["section"] != parent.section for record in children):
            raise ValueError(f"Validation failed: {parent.id} lost its section metadata.")
        if any(record["parent_titles"] != parent.parent_titles for record in children):
            raise ValueError(f"Validation failed: {parent.id} lost its parent-title metadata.")

        reconstructed = canonical_text(" ".join(str(record["text"]) for record in children))
        if reconstructed != canonical_text(parent.text):
            raise ValueError(f"Validation failed: {parent.id} is not fully covered by its child chunks.")

    hard_limit_count = sum(int(record["word_count"]) > HARD_MAX_WORDS for record in records)
    if hard_limit_count:
        raise ValueError(f"Validation failed: {hard_limit_count} chunks exceed the hard word limit.")

    actual_review = REVIEW_MARKDOWN.read_text(encoding="utf-8")
    expected_review = render_review_markdown(jsonl_records, len(structural_chunks))
    if actual_review != expected_review:
        raise ValueError("Validation failed: review Markdown does not exactly match the JSONL records.")

    return {
        "coverage_checked_parent_chunks": len(structural_chunks),
        "unique_retrieval_chunk_ids": len(record_ids),
        "hard_limit_exceeded_chunk_count": hard_limit_count,
    }


def main() -> None:
    if not SOURCE_PDF.exists():
        raise FileNotFoundError(f"S17 source PDF not found: {SOURCE_PDF}")

    structural_chunks, page_count = build_structural_chunks(SOURCE_PDF)
    records = build_retrieval_chunks(structural_chunks)
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_JSONL.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    REVIEW_MARKDOWN.write_text(render_review_markdown(records, len(structural_chunks)), encoding="utf-8")
    validation = validate_outputs(structural_chunks, records)

    split_method_counts = Counter(str(record["split_method"]) for record in records)
    split_parent_count = sum(
        len([record for record in records if record["parent_chunk_id"] == parent.id]) > 1
        for parent in structural_chunks
    )
    report = {
        "source_file": str(SOURCE_PDF.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "page_count": page_count,
        "structural_chunk_count": len(structural_chunks),
        "retrieval_chunk_count": len(records),
        "split_parent_chunk_count": split_parent_count,
        "target_word_limit": TARGET_WORDS,
        "hard_word_limit": HARD_MAX_WORDS,
        "split_method_counts": dict(sorted(split_method_counts.items())),
        "output_file": str(OUTPUT_JSONL.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "review_output_file": str(REVIEW_MARKDOWN.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "validation": {"status": "passed", **validation},
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print("\nChunks produced from section 2.3.2:")
    for record in records:
        if record["section"] == "2.3.2":
            print(f"- {record['id']} ({record['word_count']} words, {record['split_method']}): {str(record['text'])[:120]}")


if __name__ == "__main__":
    main()
