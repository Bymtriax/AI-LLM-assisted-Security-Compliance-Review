"""Extract retrieval records from one supplied English S17 PDF."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader

from corpus_builder.models import CorpusRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOCUMENT = "S17"
VERSION = "8.2"
LANGUAGE = "en"
TARGET_WORDS = 220
HARD_MAX_WORDS = 300

TOP_SECTION_RE = re.compile(r"^(\d+)\.\s+([A-Z][A-Z &,/\-]+)$")
SUBSECTION_RE = re.compile(r"^(\d+\.\d+)\.\s+(.+)$")
CONTROL_RE = re.compile(r"^(\d+\.\d+\.\d+)\.?\s+(.+)$")
PAGE_LABEL_RE = re.compile(r"^Ref\. No\.\s*:\s*S17\s+(.+)$")
ENUMERATED_ITEM_RE = re.compile(r"^[a-z]\)\s+", re.IGNORECASE)
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
PDF_BULLET_RE = re.compile(r"[\uf09f\u2022]")
DISPLAY_BULLET = "•"
TITLE_CONNECTORS = {"and", "of", "the", "in", "for", "to", "on", "with", "by", "&"}


@dataclass
class _ActiveChunk:
    kind: str
    section: str
    parent_titles: list[str]
    pdf_page_start: int
    printed_page_start: str | None
    lines: list[str | None] = field(default_factory=list)


@dataclass
class _StructuralChunk:
    id: str
    kind: str
    section: str
    parent_titles: list[str]
    pdf_page_start: int
    printed_page_start: str | None
    lines: list[str | None]
    source_file: str

    @property
    def text(self) -> str:
        return _clean_text(_join_lines(self.lines))


@dataclass
class _SemanticUnit:
    text: str
    kind: str


@dataclass
class _RetrievalPiece:
    text: str
    split_method: str


def handle_s17(pdf_path: Path) -> list[CorpusRecord]:
    """Convert one supplied English S17 PDF into corpus records."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"S17 source PDF not found: {pdf_path}")

    structural_chunks = _extract_structural_chunks(pdf_path)
    records = _build_records(structural_chunks)
    _validate_records(records)
    return records


def _normalise_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", PDF_BULLET_RE.sub(DISPLAY_BULLET, text)).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:[/-][A-Za-z0-9]+)*", text))


def _join_lines(lines: list[str | None]) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line is None:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _extract_page_lines(page_text: str) -> tuple[list[str | None], str | None]:
    lines: list[str | None] = []
    printed_page: str | None = None
    pending_blank = False

    for raw_line in page_text.splitlines():
        line = _normalise_line(raw_line)
        if not line:
            pending_blank = bool(lines)
            continue
        if line.startswith("BASELINE IT SECURITY POLICY") or line == "INFORMATION SECURITY":
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


def _make_structural_chunk(
    active: _ActiveChunk,
    counters: Counter[str],
    source_file: str,
) -> _StructuralChunk | None:
    if not _clean_text(_join_lines(active.lines)):
        return None
    suffix = "overview" if active.kind == "overview" else "clause"
    base_id = f"{DOCUMENT}-v{VERSION}-{active.section}-{suffix}"
    counters[base_id] += 1
    chunk_id = base_id if counters[base_id] == 1 else f"{base_id}-{counters[base_id]}"
    return _StructuralChunk(
        id=chunk_id,
        kind=active.kind,
        section=active.section,
        parent_titles=active.parent_titles,
        pdf_page_start=active.pdf_page_start,
        printed_page_start=active.printed_page_start,
        lines=active.lines.copy(),
        source_file=source_file,
    )


def _extract_structural_chunks(pdf_path: Path) -> list[_StructuralChunk]:
    reader = PdfReader(str(pdf_path))
    chunks: list[_StructuralChunk] = []
    counters: Counter[str] = Counter()
    current_top: tuple[str, str] | None = None
    current_sub: tuple[str, str] | None = None
    active: _ActiveChunk | None = None
    try:
        source_file = pdf_path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        source_file = str(pdf_path.resolve())

    def parent_titles() -> list[str]:
        titles: list[str] = []
        if current_top:
            titles.append(f"{current_top[0]}. {current_top[1]}")
        if current_sub:
            titles.append(f"{current_sub[0]}. {current_sub[1]}")
        return titles

    def flush_active() -> None:
        nonlocal active
        if active is not None:
            chunk = _make_structural_chunk(active, counters, source_file)
            if chunk is not None:
                chunks.append(chunk)
        active = None

    # Physical pages 1-6 contain cover material, history and contents.
    for pdf_page, page in enumerate(reader.pages, start=1):
        if pdf_page < 7:
            continue
        lines, printed_page = _extract_page_lines(page.extract_text() or "")
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

            control_match = CONTROL_RE.match(line)
            if control_match:
                flush_active()
                active = _ActiveChunk(
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
                active = _ActiveChunk(
                    kind="overview",
                    section=current_sub[0] if current_sub else current_top[0],
                    parent_titles=parent_titles(),
                    pdf_page_start=pdf_page,
                    printed_page_start=printed_page,
                )
            active.lines.append(line)

    flush_active()
    return chunks


def _is_title_line(line: str) -> bool:
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
    title_words = sum(
        token[0].isupper() or token.isupper() or token.lower() in TITLE_CONNECTORS
        for token in tokens
    )
    return title_words / len(tokens) >= 0.8


def _semantic_units(lines: list[str | None]) -> list[_SemanticUnit]:
    units: list[_SemanticUnit] = []
    current: list[str] = []
    current_kind = "paragraph"

    def flush() -> None:
        nonlocal current
        text = _clean_text(" ".join(current))
        if text:
            units.append(_SemanticUnit(text, current_kind))
        current = []

    for line in lines:
        if line is None:
            flush()
            current_kind = "paragraph"
        elif PDF_BULLET_RE.search(line):
            fragments = PDF_BULLET_RE.split(line)
            if fragments[0].strip():
                current.append(fragments[0].strip())
            flush()
            for fragment in fragments[1:]:
                if fragment.strip():
                    flush()
                    current_kind = "bullet_item"
                    current = [DISPLAY_BULLET, fragment.strip()]
        elif ENUMERATED_ITEM_RE.match(line):
            flush()
            current_kind = "enumerated_item"
            current = [line]
        elif _is_title_line(line):
            flush()
            current_kind = "internal_heading"
            current = [line]
        else:
            current.append(line)
    flush()
    return units


def _split_to_target(text: str, method: str) -> list[_RetrievalPiece]:
    text = _clean_text(text)
    if _word_count(text) <= TARGET_WORDS:
        return [_RetrievalPiece(text, method)]
    sentences = [part.strip() for part in SENTENCE_BOUNDARY_RE.split(text) if part.strip()]
    if len(sentences) <= 1:
        return [_RetrievalPiece(text, f"{method}_needs_review")]

    pieces: list[_RetrievalPiece] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = _clean_text(" ".join([*current, sentence]))
        if current and _word_count(candidate) > TARGET_WORDS:
            pieces.append(_RetrievalPiece(_clean_text(" ".join(current)), "sentence_boundary"))
            current = [sentence]
        else:
            current.append(sentence)
    if current:
        pieces.append(_RetrievalPiece(_clean_text(" ".join(current)), "sentence_boundary"))
    return pieces


def _retrieval_pieces(chunk: _StructuralChunk) -> list[_RetrievalPiece]:
    if _word_count(chunk.text) <= TARGET_WORDS:
        return [_RetrievalPiece(chunk.text, "unchanged")]
    units = _semantic_units(chunk.lines)
    if not units:
        return _split_to_target(chunk.text, "sentence_boundary")

    if len(units) > 1 and units[0].kind == "internal_heading" and _word_count(units[0].text) <= 12:
        units[1] = _SemanticUnit(_clean_text(f"{units[0].text} {units[1].text}"), units[1].kind)
        units = units[1:]

    pieces: list[_RetrievalPiece] = []
    paragraph_buffer: list[str] = []

    def flush_paragraphs() -> None:
        nonlocal paragraph_buffer
        if paragraph_buffer:
            pieces.extend(_split_to_target(" ".join(paragraph_buffer), "paragraph_group"))
        paragraph_buffer = []

    for unit in units:
        if unit.kind == "paragraph":
            candidate = _clean_text(" ".join([*paragraph_buffer, unit.text]))
            if paragraph_buffer and _word_count(candidate) > TARGET_WORDS:
                flush_paragraphs()
            paragraph_buffer.append(unit.text)
        else:
            flush_paragraphs()
            pieces.extend(_split_to_target(unit.text, unit.kind))
    flush_paragraphs()
    return pieces


def _record_text(chunk: _StructuralChunk, body: str) -> str:
    """Add the retrieval context that is stored with each S17 record."""
    return "\n".join(
        [
            f"Section: {chunk.section}",
            f"Parent sections: {' > '.join(chunk.parent_titles)}",
            f"Text: {body}",
        ]
    )


def _build_records(chunks: list[_StructuralChunk]) -> list[CorpusRecord]:
    records: list[CorpusRecord] = []
    for chunk in chunks:
        pieces = _retrieval_pieces(chunk)
        for part_number, piece in enumerate(pieces, start=1):
            record_text = _record_text(chunk, piece.text)
            records.append(
                CorpusRecord(
                    id=f"{chunk.id}-part-{part_number:02d}",
                    text=record_text,
                    metadata={
                        "document": DOCUMENT,
                        "version": VERSION,
                        "language": LANGUAGE,
                        "section": chunk.section,
                        "parent_titles": " > ".join(chunk.parent_titles),
                        "parent_chunk_id": chunk.id,
                        "source_kind": chunk.kind,
                        "split_method": piece.split_method,
                        "part_number": part_number,
                        "part_count": len(pieces),
                        "pdf_page_start": chunk.pdf_page_start,
                        "printed_page_start": chunk.printed_page_start or "",
                        "word_count": _word_count(piece.text),
                        "text_sha256": sha256(record_text.encode("utf-8")).hexdigest(),
                        "source_file": chunk.source_file,
                    },
                )
            )
    return records


def _validate_records(records: list[CorpusRecord]) -> None:
    if not records:
        raise ValueError("S17 extraction produced no records.")
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("S17 extraction produced duplicate record IDs.")
    if any(not record.text.strip() for record in records):
        raise ValueError("S17 extraction produced an empty record text.")
    oversized = [
        record.id
        for record in records
        if int(record.metadata["word_count"]) > HARD_MAX_WORDS
    ]
    if oversized:
        raise ValueError(f"S17 records exceed the hard word limit: {oversized}")
