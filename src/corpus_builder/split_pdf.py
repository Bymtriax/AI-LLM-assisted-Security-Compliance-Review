"""Split English S17/G3 PDFs into local JSON records without building a database.

The standalone workflow is extracted from handle_s17; the existing builder keeps
using its original handler until a separate refactor integrates these JSON files.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader

from corpus_builder.models import CorpusRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LANGUAGE = "en"
TARGET_WORDS = 220
HARD_MAX_WORDS = 300

TOP_SECTION_RE = re.compile(r"^(\d+)\.?\s+([A-Z][A-Z &,/\-]+)$")
SUBSECTION_RE = re.compile(r"^(\d+\.\d+)\.?\s+([A-Z].+)$")
CONTROL_RE = re.compile(r"^(\d+\.\d+\.\d+)\.?\s+(.+)$")
PAGE_LABEL_RE = re.compile(r"^Ref\.\s*No\.\s*:\s*(S17|G3)\s+(.+)$")
APPENDIX_RE = re.compile(r"^APPENDIX ([A-Z])\s+(.+)$")
LETTER_HEADING_RE = re.compile(r"^\(([a-z])\)\s+(.+)$")
TOC_LEADER_RE = re.compile(r"\s*\.{2,}.*$")
ENUMERATED_ITEM_RE = re.compile(r"^(?:[a-z]\)|\([a-z]\)|\d+\.)\s+", re.IGNORECASE)
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
PDF_BULLET_RE = re.compile(r"[\uf09f\u2022]")
DISPLAY_BULLET = "•"
TITLE_CONNECTORS = {"and", "of", "the", "in", "for", "to", "on", "with", "by", "&"}
PDF_SOURCES: dict[str, tuple[str, Path]] = {
    "S17": ("8.2", PROJECT_ROOT / "data/raw/standards/en/S17_EN_v8.2_2025-04.pdf"),
    "G3": ("10.2", PROJECT_ROOT / "data/raw/standards/en/G3_EN_v10.2_2025-04.pdf"),
}


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


def split_pdf(pdf_path: Path, *, document: str, version: str) -> list[CorpusRecord]:
    """Convert one English S17 or G3 PDF into traceable corpus records."""
    if document not in PDF_SOURCES:
        raise ValueError("Supported documents are S17 and G3.")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("PDF version must be a non-empty string.")
    if not pdf_path.is_file():
        raise FileNotFoundError(f"{document} source PDF not found: {pdf_path}")

    structural_chunks = _extract_structural_chunks(pdf_path, document, version)
    records = _build_records(structural_chunks, document, version)
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


def _extract_page_lines(
    page_text: str, document: str,
) -> tuple[list[str | None], str | None]:
    lines: list[str | None] = []
    printed_page: str | None = None
    pending_blank = False

    raw_lines = page_text.splitlines()
    # These PDFs extract their running header and footer before the body. Drop
    # the whole header block, including wrapped titles and table border glyphs.
    first_line = next((line.strip() for line in raw_lines if line.strip()), "")
    if first_line.startswith(("BASELINE IT SECURITY POLICY", "IT SECURITY GUIDELINES")):
        for index, raw_line in enumerate(raw_lines):
            if PAGE_LABEL_RE.match(_normalise_line(raw_line)):
                raw_lines = raw_lines[index:]
                break

    for raw_line in raw_lines:
        line = _normalise_line(raw_line)
        if not line:
            pending_blank = bool(lines)
            continue
        if line.startswith(("BASELINE IT SECURITY POLICY", "IT SECURITY GUIDELINES")):
            continue
        page_match = PAGE_LABEL_RE.match(line)
        if page_match:
            if page_match.group(1) != document:
                raise ValueError(f"PDF reference does not match document {document}.")
            printed_page = page_match.group(2).strip()
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
    document: str,
    version: str,
) -> _StructuralChunk | None:
    if not _clean_text(_join_lines(active.lines)):
        return None
    suffix = "overview" if active.kind == "overview" else "clause"
    base_id = f"{document}-v{version}-{active.section}-{suffix}"
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


def _toc_letter_titles(
    pages: list[tuple[list[str | None], str | None]],
) -> dict[str, str]:
    """Read G3's lettered titles, including wrapped entries, from its contents."""
    titles: dict[str, str] = {}
    subsection: str | None = None
    pending_key: str | None = None
    pending_title: list[str] = []
    for lines, printed_page in pages:
        if not printed_page or not printed_page.startswith("iii-"):
            continue
        for line in lines:
            if line is None:
                continue
            sub_match = SUBSECTION_RE.match(line)
            letter_match = LETTER_HEADING_RE.match(line)
            if sub_match:
                subsection = sub_match.group(1)
                pending_key = None
                pending_title = []
            elif letter_match and subsection:
                pending_key = f"{subsection}({letter_match.group(1)})"
                pending_title = [TOC_LEADER_RE.sub("", letter_match.group(2)).strip()]
            elif pending_key:
                pending_title.append(TOC_LEADER_RE.sub("", line).strip())
            if pending_key and TOC_LEADER_RE.search(line):
                titles[pending_key] = _clean_text(" ".join(pending_title))
                pending_key = None
                pending_title = []
    return titles


def _extract_structural_chunks(
    pdf_path: Path, document: str, version: str,
) -> list[_StructuralChunk]:
    reader = PdfReader(str(pdf_path))
    pages = [_extract_page_lines(page.extract_text() or "", document) for page in reader.pages]
    letter_titles = _toc_letter_titles(pages) if document == "G3" else {}
    chunks: list[_StructuralChunk] = []
    counters: Counter[str] = Counter()
    current_top: tuple[str, str] | None = None
    current_sub: tuple[str, str] | None = None
    active: _ActiveChunk | None = None
    body_started = False
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
            chunk = _make_structural_chunk(active, counters, source_file, document, version)
            if chunk is not None:
                chunks.append(chunk)
        active = None

    for pdf_page, (lines, printed_page) in enumerate(pages, start=1):
        # S17 and G3 have different front-matter lengths. Printed page 1 marks
        # the body in both; later unlabelled pages inside G3 Appendix A are kept.
        if not body_started:
            body_started = printed_page == "1"
        if not body_started:
            continue
        skip_until = 0
        for index, line in enumerate(lines):
            if index < skip_until:
                continue
            if line is None:
                if active is not None and active.lines and active.lines[-1] is not None:
                    active.lines.append(None)
                continue

            top_match = TOP_SECTION_RE.match(line)
            appendix_match = APPENDIX_RE.match(line)
            if top_match or appendix_match:
                flush_active()
                match = appendix_match or top_match
                assert match is not None
                title = match.group(2).strip()
                skip_until = index + 1
                # Join wrapped uppercase chapter/appendix titles.
                while skip_until < len(lines):
                    continuation = lines[skip_until]
                    if (
                        continuation is None
                        or not continuation.isupper()
                        or TOP_SECTION_RE.match(continuation)
                        or SUBSECTION_RE.match(continuation)
                        or CONTROL_RE.match(continuation)
                        or APPENDIX_RE.match(continuation)
                    ):
                        break
                    title = f"{title} {continuation}"
                    skip_until += 1
                section = f"APPENDIX-{match.group(1)}" if appendix_match else match.group(1)
                current_top = (section, title)
                current_sub = None
                continue

            control_match = CONTROL_RE.match(line)
            if control_match and current_top and control_match.group(1).split(".")[0] == current_top[0]:
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
            if (
                subsection_match and current_top
                and subsection_match.group(1).split(".")[0] == current_top[0]
            ):
                flush_active()
                current_sub = (subsection_match.group(1), subsection_match.group(2).strip())
                continue

            letter_match = LETTER_HEADING_RE.match(line)
            letter_section = (
                f"{current_sub[0]}({letter_match.group(1)})"
                if current_sub and letter_match else ""
            )
            title = letter_match.group(2).strip() if letter_match else ""
            expected_title = letter_titles.get(letter_section)
            is_letter_heading = bool(
                expected_title and (
                    expected_title.casefold().startswith(title.casefold()) or _is_title_line(title)
                )
            ) if letter_titles else _is_title_line(title)
            if document == "G3" and letter_section and is_letter_heading:
                # The contents disambiguate one-word, hyphenated and wrapped
                # headings from similarly numbered lists inside the body.
                skip_until = index + 1
                while expected_title and title.casefold() != expected_title.casefold():
                    if skip_until >= len(lines) or lines[skip_until] is None:
                        break
                    candidate = f"{title} {lines[skip_until]}"
                    if not expected_title.casefold().startswith(candidate.casefold()):
                        break
                    title = candidate
                    skip_until += 1
                flush_active()
                active = _ActiveChunk(
                    kind="lettered_clause",
                    section=letter_section,
                    parent_titles=parent_titles(),
                    pdf_page_start=pdf_page,
                    printed_page_start=printed_page,
                    lines=[title],
                )
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
    if len(sentences) <= 1 and _word_count(text) <= HARD_MAX_WORDS:
        return [_RetrievalPiece(text, f"{method}_needs_review")]

    pieces: list[_RetrievalPiece] = []
    current: list[str] = []
    for sentence in sentences:
        if _word_count(sentence) > HARD_MAX_WORDS:
            if current:
                pieces.append(_RetrievalPiece(_clean_text(" ".join(current)), "sentence_boundary"))
                current = []
            # Preserve every character while bounding unusually long sentences
            # or text extracted from tables without sentence punctuation.
            words = list(re.finditer(r"[A-Za-z0-9]+(?:[/-][A-Za-z0-9]+)*", sentence))
            start = 0
            for boundary in range(TARGET_WORDS, len(words), TARGET_WORDS):
                end = words[boundary].start()
                pieces.append(_RetrievalPiece(sentence[start:end].strip(), "word_boundary"))
                start = end
            pieces.append(_RetrievalPiece(sentence[start:].strip(), "word_boundary"))
            continue
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
    """Keep the existing three-line retrieval text contract."""
    return "\n".join(
        [
            f"Section: {chunk.section}",
            f"Parent sections: {' > '.join(chunk.parent_titles)}",
            f"Text: {body}",
        ]
    )


def _build_records(
    chunks: list[_StructuralChunk], document: str, version: str,
) -> list[CorpusRecord]:
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
                        "document": document,
                        "version": version,
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
        raise ValueError("PDF extraction produced no records; expected printed page 1 and section headings.")
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("PDF extraction produced duplicate record IDs.")
    if any(not record.text.strip() for record in records):
        raise ValueError("PDF extraction produced an empty record text.")
    oversized = [
        record.id
        for record in records
        if int(record.metadata["word_count"]) > HARD_MAX_WORDS
    ]
    if oversized:
        raise ValueError(f"PDF records exceed the hard word limit: {oversized}")


def write_records_json(records: list[CorpusRecord], output_path: Path) -> None:
    """Write a UTF-8 JSON array containing id, text and flat metadata."""
    _validate_records(records)
    if output_path.suffix.lower() != ".json":
        raise ValueError("Processed records must be saved to a .json file.")
    payload = [
        {"id": record.id, "text": record.text, "metadata": dict(record.metadata)}
        for record in records
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    """Export both configured English PDFs, or only selected documents."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", nargs="+", choices=PDF_SOURCES, default=list(PDF_SOURCES))
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/processed")
    args = parser.parse_args(argv)
    exports: list[tuple[str, list[CorpusRecord]]] = []
    for document in dict.fromkeys(args.document):
        version, pdf_path = PDF_SOURCES[document]
        records = split_pdf(pdf_path, document=document, version=version)
        exports.append((document, records))
    for document, records in exports:
        output_path = args.output_dir / f"{document.lower()}_en_chunks.json"
        write_records_json(records, output_path)
        print(f"{document}: saved {len(records)} records to {output_path}")


if __name__ == "__main__":
    main()
