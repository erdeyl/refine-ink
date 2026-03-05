#!/usr/bin/env python3
"""
pdf_to_markdown.py - Convert academic PDF papers to clean Markdown.

Uses pymupdf4llm for high-quality PDF-to-Markdown conversion with
automatic multi-column layout handling, and extracts a structured
reference list into a companion JSON file.

Usage:
    python pdf_to_markdown.py input.pdf [--output-dir DIR]

Outputs:
    <filename>_converted.md      - Full Markdown text
    <filename>_references.json   - Structured reference entries
    figures/<filename>_fig_p<page>_<idx>.<ext>  - Extracted figure images (with --extract-figures)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_INPUT_ERROR = 1        # bad arguments / missing file
EXIT_CONVERSION_ERROR = 2   # pymupdf4llm failure
EXIT_IO_ERROR = 3           # cannot write output


# ---------------------------------------------------------------------------
# Reference extraction helpers
# ---------------------------------------------------------------------------

# Patterns that typically start the reference / bibliography section
_REF_HEADING_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"^#{1,3}\s*(References|Bibliography|Works\s+Cited|Literature\s+Cited"
        r"|Cited\s+References|Reference\s+List)\s*$",
        re.IGNORECASE | re.MULTILINE,
    ),
    # Some PDFs produce bold headings instead of Markdown headings
    re.compile(
        r"^\*{1,2}(References|Bibliography|Works\s+Cited|Literature\s+Cited"
        r"|Cited\s+References|Reference\s+List)\*{1,2}\s*$",
        re.IGNORECASE | re.MULTILINE,
    ),
    # Plain text heading (all-caps or title-case on its own line)
    re.compile(
        r"^(REFERENCES|BIBLIOGRAPHY|References|Bibliography)\s*$",
        re.MULTILINE,
    ),
]

# Headings that would mark the END of the references section
_NEXT_SECTION_RE = re.compile(
    r"^#{1,3}\s+\S|"
    r"^\*{1,2}[A-Z][A-Za-z ]+\*{1,2}\s*$|"
    r"^(Appendix|Supplementary|Acknowledgment|Acknowledge)",
    re.IGNORECASE | re.MULTILINE,
)

# DOI patterns
_DOI_RE = re.compile(r"(?:doi[:\s]*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,}/\S+)", re.IGNORECASE)

# Year (four digits, commonly 19xx or 20xx)
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

# Numbered reference: starts with [1], 1., (1), etc.
_NUMBERED_RE = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)\.\s|\((\d+)\))\s*")

# Author-year style start for non-numbered bibliographies.
_AUTHOR_YEAR_START_RE = re.compile(
    r"^[A-ZÀ-ÖØ-ÝŐŰ][A-Za-zÀ-ÖØ-öø-ÿŐőŰű'’\-]+(?:\s+[A-ZÀ-ÖØ-ÝŐŰ][A-Za-zÀ-ÖØ-öø-ÿŐőŰű'’\-]+){0,2},"
)


def _find_references_section(md_text: str) -> Optional[str]:
    """Return the raw text of the references section, or None."""
    matches: list[re.Match[str]] = []
    for pattern in _REF_HEADING_PATTERNS:
        matches.extend(pattern.finditer(md_text))

    if not matches:
        return None

    # References are typically near the end; use the latest heading match.
    best_match = max(matches, key=lambda m: m.start())
    best_start = best_match.end()

    # Find where the next major section starts after references
    remainder = md_text[best_start:]
    end_match = _NEXT_SECTION_RE.search(remainder)
    if end_match:
        remainder = remainder[: end_match.start()]

    return remainder.strip()


def _looks_like_new_reference_line(stripped: str, raw_line: str) -> bool:
    """Heuristic for non-numbered references that start on a new line."""
    if _NUMBERED_RE.match(stripped):
        return True

    # Indented lines are usually continuations of the previous entry.
    if raw_line.startswith((" ", "\t")):
        return False

    # Require an early year marker to avoid splitting on title-case continuation lines.
    has_year_early = bool(
        re.search(r"\((?:19|20)\d{2}[a-z]?\)", stripped[:120])
        or re.search(r"\b(?:19|20)\d{2}[a-z]?\b", stripped[:120])
    )
    if not has_year_early:
        return False

    if _AUTHOR_YEAR_START_RE.match(stripped):
        return True

    # Fallback for styles like "Surname et al. (2020) ..."
    return bool(re.match(r"^[A-ZÀ-ÖØ-ÝŐŰ][^.!?]{0,100}\((?:19|20)\d{2}[a-z]?\)", stripped))


def _split_references(ref_block: str) -> list[str]:
    """Split a references block into individual reference strings."""
    lines = ref_block.splitlines()
    entries: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Blank line -> flush current entry
            if current:
                entries.append(" ".join(current))
                current = []
            continue

        # Split on explicit numbered markers and author-year new-entry cues.
        if current and _looks_like_new_reference_line(stripped, line):
            entries.append(" ".join(current))
            current = []

        current.append(stripped)

    if current:
        entries.append(" ".join(current))

    return [e for e in entries if len(e) > 15]  # discard very short fragments


def _extract_authors(text: str) -> str:
    """Heuristic extraction of author names from the beginning of a reference."""
    # Remove leading number markers
    cleaned = _NUMBERED_RE.sub("", text).strip()

    # Common pattern: authors come before the year or before a title in quotes/italics
    # Try splitting on the first year occurrence
    year_match = _YEAR_RE.search(cleaned)
    if year_match:
        before_year = cleaned[: year_match.start()].strip().rstrip("(.,;")
        if 5 < len(before_year) < 500:
            return before_year

    # Fallback: take text up to the first period
    dot_pos = cleaned.find(".")
    if 5 < dot_pos < 300:
        return cleaned[:dot_pos].strip()

    return ""


def _extract_title(text: str) -> str:
    """Heuristic extraction of the title from a reference entry."""
    cleaned = _NUMBERED_RE.sub("", text).strip()

    # Try to find a quoted title
    quoted = re.search(r'["\u201c](.+?)["\u201d]', cleaned)
    if quoted and len(quoted.group(1)) > 10:
        return quoted.group(1).strip()

    # Try to find an italic title (*title* or _title_)
    italic = re.search(r"[*_](.+?)[*_]", cleaned)
    if italic and len(italic.group(1)) > 10:
        return italic.group(1).strip()

    # Fallback: text between first period and second period after the year
    year_match = _YEAR_RE.search(cleaned)
    if year_match:
        after_year = cleaned[year_match.end():].strip().lstrip(".)],;: ")
        dot_pos = after_year.find(".")
        if dot_pos > 10:
            return after_year[:dot_pos].strip()

    return ""


def _extract_journal(text: str) -> str:
    """Heuristic extraction of journal name."""
    # Look for italic text that is NOT the title (often the journal)
    italics = re.findall(r"[*_]([^*_]+)[*_]", text)
    if len(italics) >= 2:
        # Second italic block is often the journal
        return italics[1].strip()
    if len(italics) == 1:
        candidate = italics[0].strip()
        # If it looks like a journal (contains uppercase, not too long)
        if len(candidate) < 120:
            return candidate

    return ""


def _parse_reference(raw_text: str) -> dict:
    """Parse a single reference string into a structured dict."""
    doi_match = _DOI_RE.search(raw_text)
    year_match = _YEAR_RE.search(raw_text)

    return {
        "title": _extract_title(raw_text),
        "authors": _extract_authors(raw_text),
        "year": year_match.group(1) if year_match else "",
        "doi": doi_match.group(1).rstrip(".,;)") if doi_match else "",
        "journal": _extract_journal(raw_text),
        "raw_text": raw_text.strip(),
    }


def extract_references(md_text: str) -> list[dict]:
    """Extract structured references from the Markdown text."""
    ref_section = _find_references_section(md_text)
    if not ref_section:
        return []

    entries = _split_references(ref_section)
    return [_parse_reference(entry) for entry in entries]


# ---------------------------------------------------------------------------
# Figure extraction
# ---------------------------------------------------------------------------

# Minimum dimensions (pixels) to consider an image a figure vs an icon/logo
_MIN_FIGURE_WIDTH = 150
_MIN_FIGURE_HEIGHT = 100


def extract_figures(pdf_path: Path, output_dir: Path) -> list[dict]:
    """Extract embedded images from a PDF that likely represent figures.

    Returns a list of dicts with keys: page, index, path, width, height.
    """
    try:
        import pymupdf  # type: ignore
    except ImportError:
        print("Warning: pymupdf not available for figure extraction", file=sys.stderr)
        return []

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    stem = pdf_path.stem
    extracted: list[dict] = []

    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        print(f"Warning: could not open PDF for figure extraction: {exc}", file=sys.stderr)
        return []

    seen_xrefs: set[int] = set()
    try:
        for page_num in range(doc.page_count):
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    continue

                width = base_image.get("width", 0)
                height = base_image.get("height", 0)

                if width < _MIN_FIGURE_WIDTH or height < _MIN_FIGURE_HEIGHT:
                    continue

                img_bytes = base_image.get("image")
                if not img_bytes:
                    continue
                ext = base_image.get("ext", "png")
                filename = f"{stem}_fig_p{page_num + 1}_{img_idx}.{ext}"
                img_path = figures_dir / filename

                try:
                    img_path.write_bytes(img_bytes)
                    extracted.append({
                        "page": page_num + 1,
                        "index": img_idx,
                        "path": str(img_path),
                        "width": width,
                        "height": height,
                    })
                except OSError:
                    continue
    finally:
        doc.close()

    if extracted:
        print(f"Figures extracted: {len(extracted)} images saved to {figures_dir}")
    else:
        print("Figures: no extractable figure images found in PDF")

    return extracted


# ---------------------------------------------------------------------------
# Conversion statistics
# ---------------------------------------------------------------------------

def _compute_stats(md_text: str, page_count: int) -> dict:
    """Compute conversion statistics from the Markdown output."""
    words = len(md_text.split())
    sections = len(re.findall(r"^#{1,6}\s+", md_text, re.MULTILINE))
    # Count markdown tables (lines starting with |)
    table_rows = re.findall(r"^\|.+\|$", md_text, re.MULTILINE)
    # A table is a contiguous block of | rows.  Count separator rows as proxy.
    table_count = len(re.findall(r"^\|[\s\-:|]+\|$", md_text, re.MULTILINE))

    return {
        "pages": page_count,
        "words": words,
        "sections": sections,
        "tables": table_count,
    }


def _print_stats(stats: dict) -> None:
    print("\n--- Conversion Statistics ---")
    print(f"  Pages:    {stats['pages']}")
    print(f"  Words:    {stats['words']}")
    print(f"  Sections: {stats['sections']}")
    print(f"  Tables:   {stats['tables']}")
    if "figures" in stats:
        print(f"  Figures:  {stats['figures']}")
    print("-----------------------------\n")


# ---------------------------------------------------------------------------
# Main conversion logic
# ---------------------------------------------------------------------------

def convert_pdf(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    do_extract_figures: bool = False,
) -> int:
    """Convert a PDF to Markdown + references JSON. Returns an exit code."""
    # ------------------------------------------------------------------
    # 1. Validate input
    # ------------------------------------------------------------------
    if not pdf_path.is_file():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if pdf_path.suffix.lower() != ".pdf":
        print(f"Error: not a PDF file: {pdf_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    # ------------------------------------------------------------------
    # 2. Determine output paths
    # ------------------------------------------------------------------
    if output_dir is None:
        output_dir = pdf_path.parent
    output_dir = Path(output_dir)

    if not output_dir.is_dir():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"Error: cannot create output directory: {exc}", file=sys.stderr)
            return EXIT_IO_ERROR

    stem = pdf_path.stem
    md_path = output_dir / f"{stem}_converted.md"
    refs_path = output_dir / f"{stem}_references.json"

    # ------------------------------------------------------------------
    # 3. Convert PDF -> Markdown via pymupdf4llm
    # ------------------------------------------------------------------
    try:
        import pymupdf4llm  # type: ignore
        import pymupdf       # type: ignore  (fitz)
    except ImportError as exc:
        print(
            f"Error: required package not installed: {exc}\n"
            "Install with:  pip install pymupdf4llm",
            file=sys.stderr,
        )
        return EXIT_CONVERSION_ERROR

    print(f"Converting: {pdf_path}")

    try:
        md_text: str = pymupdf4llm.to_markdown(
            str(pdf_path),
            show_progress=False,
        )
    except Exception as exc:
        print(f"Error during PDF conversion: {exc}", file=sys.stderr)
        return EXIT_CONVERSION_ERROR

    # Get page count from PyMuPDF directly
    try:
        doc = pymupdf.open(str(pdf_path))
        page_count = doc.page_count
        doc.close()
    except Exception:
        page_count = 0

    # ------------------------------------------------------------------
    # 4. Post-process: light clean-up
    # ------------------------------------------------------------------
    # Collapse runs of 3+ blank lines into 2
    md_text = re.sub(r"\n{4,}", "\n\n\n", md_text)
    # Strip trailing whitespace on each line
    md_text = "\n".join(line.rstrip() for line in md_text.splitlines()) + "\n"

    # ------------------------------------------------------------------
    # 5. Write Markdown output
    # ------------------------------------------------------------------
    try:
        md_path.write_text(md_text, encoding="utf-8")
        print(f"Markdown saved: {md_path}")
    except OSError as exc:
        print(f"Error writing Markdown: {exc}", file=sys.stderr)
        return EXIT_IO_ERROR

    # ------------------------------------------------------------------
    # 6. Extract and write references
    # ------------------------------------------------------------------
    references = extract_references(md_text)
    try:
        refs_path.write_text(
            json.dumps(references, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"References saved: {refs_path}  ({len(references)} entries)")
    except OSError as exc:
        print(f"Error writing references JSON: {exc}", file=sys.stderr)
        return EXIT_IO_ERROR

    # ------------------------------------------------------------------
    # 7. Extract figures (optional)
    # ------------------------------------------------------------------
    figures: list[dict] = []
    if do_extract_figures:
        figures = extract_figures(pdf_path, output_dir)

    # ------------------------------------------------------------------
    # 8. Print statistics
    # ------------------------------------------------------------------
    stats = _compute_stats(md_text, page_count)
    stats["figures"] = len(figures)
    _print_stats(stats)

    return EXIT_OK


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert an academic PDF to clean Markdown with reference extraction.",
    )
    parser.add_argument(
        "pdf",
        type=Path,
        help="Path to the input PDF file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for output files (default: same directory as the PDF).",
    )
    parser.add_argument(
        "--extract-figures",
        action="store_true",
        default=False,
        help="Extract embedded figure images from the PDF into a figures/ subdirectory.",
    )

    args = parser.parse_args()
    return convert_pdf(args.pdf, args.output_dir, do_extract_figures=args.extract_figures)


if __name__ == "__main__":
    sys.exit(main())
