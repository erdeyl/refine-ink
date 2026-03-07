#!/usr/bin/env python3
"""
pdf_to_markdown.py - Convert academic PDF papers to clean Markdown.

Uses pymupdf4llm for high-quality PDF-to-Markdown conversion with
automatic multi-column layout handling, and extracts a structured
reference list into a companion JSON file.

Usage:
    python pdf_to_markdown.py input.pdf [--output-dir DIR]
    python pdf_to_markdown.py input.pdf --enhanced [--output-dir DIR]

The --enhanced flag enables:
    - Page boundary markers (<!-- page N -->) for PDF-MD location mapping
    - Improved table extraction using pymupdf's structured table finder
    - Multi-column layout detection and logging

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
# Enhanced conversion helpers
# ---------------------------------------------------------------------------

def _detect_multi_column(doc) -> list[dict]:
    """Detect pages with multi-column layouts by analyzing text block x-coordinates.

    Args:
        doc: An open pymupdf document.

    Returns a list of dicts: {page, columns, gap_positions}.
    Only reports pages with 2+ detected columns.
    """
    multi_col_pages: list[dict] = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
        page_width = page.rect.width
        page_dict = page.get_text("dict", flags=0)

        # Collect x-coordinates of text block left edges
        x_starts: list[float] = []
        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:  # text block
                bbox = block.get("bbox", [0, 0, 0, 0])
                has_text = any(
                    span.get("text", "").strip()
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                )
                if has_text:
                    x_starts.append(bbox[0])

        if len(x_starts) < 4:
            continue

        # Cluster x_starts to detect columns
        # Sort and find gaps > 15% of page width
        x_sorted = sorted(set(round(x, 0) for x in x_starts))
        if len(x_sorted) < 2:
            continue

        gaps: list[float] = []
        gap_threshold = page_width * 0.15
        clusters: list[list[float]] = [[x_sorted[0]]]

        for i in range(1, len(x_sorted)):
            if x_sorted[i] - x_sorted[i - 1] > gap_threshold:
                gaps.append((x_sorted[i - 1] + x_sorted[i]) / 2)
                clusters.append([x_sorted[i]])
            else:
                clusters[-1].append(x_sorted[i])

        if len(clusters) >= 2:
            multi_col_pages.append({
                "page": page_num + 1,
                "columns": len(clusters),
                "gap_positions": [round(g, 1) for g in gaps],
            })

    return multi_col_pages


def _extract_table_markdown_from_page(page) -> list[str]:
    """Extract tables from a pymupdf page object using the structured table finder.

    Returns a list of markdown-formatted table strings.
    """
    tables_md: list[str] = []
    try:
        table_finder = page.find_tables()
    except Exception:
        return []

    for table in table_finder.tables:
        try:
            data = table.extract()
            if not data or len(data) < 2:
                continue

            # Build markdown table
            lines: list[str] = []
            # Header row
            header = data[0]
            header_cells = [str(c).strip() if c else "" for c in header]
            lines.append("| " + " | ".join(header_cells) + " |")
            # Separator
            lines.append("| " + " | ".join("---" for _ in header_cells) + " |")
            # Data rows
            for row in data[1:]:
                cells = [str(c).strip() if c else "" for c in row]
                # Pad or trim to match header column count
                while len(cells) < len(header_cells):
                    cells.append("")
                cells = cells[:len(header_cells)]
                lines.append("| " + " | ".join(cells) + " |")

            tables_md.append("\n".join(lines))
        except Exception:
            continue

    return tables_md


def _convert_page_by_page(pdf_path: Path) -> tuple[str, dict]:
    """Convert PDF page-by-page, inserting <!-- page N --> markers.

    Returns (md_text, stats_dict) where stats_dict includes
    page_markers_count and multi_column_pages.
    """
    try:
        import pymupdf4llm  # type: ignore
        import pymupdf       # type: ignore
    except ImportError as exc:
        raise ImportError(
            f"Required package not installed: {exc}\n"
            "Install with:  pip install pymupdf4llm"
        )

    doc = pymupdf.open(str(pdf_path))
    try:
        page_count = doc.page_count
        if page_count == 0:
            print("Warning: PDF has 0 pages", file=sys.stderr)
            return "", {"page_markers": 0, "table_improvements": 0,
                        "multi_column_pages": 0, "multi_column_details": []}
        pages_md: list[str] = []
        table_improvements = 0

        for page_num in range(page_count):
            # Convert single page
            try:
                page_md: str = pymupdf4llm.to_markdown(
                    str(pdf_path),
                    pages=[page_num],
                    show_progress=False,
                )
            except Exception as exc:
                print(f"  Warning: page {page_num + 1} conversion failed: {exc}", file=sys.stderr)
                page_md = f"[Page {page_num + 1} conversion failed]\n"

            # Try to improve tables on this page using the already-open doc
            page = doc[page_num]
            structured_tables = _extract_table_markdown_from_page(page)
            if structured_tables:
                md_tables_in_page = re.findall(
                    r"(?:^\|.+\|$\n?)+",
                    page_md,
                    re.MULTILINE,
                )
                # Only attempt replacement when counts match 1:1 to avoid
                # replacing a garbled table with a structured table from a
                # different physical table on the same page.
                if len(md_tables_in_page) == len(structured_tables):
                    for md_table, struct_table in zip(md_tables_in_page, structured_tables):
                        md_cols = md_table.split("\n")[0].count("|") - 1
                        struct_cols = struct_table.split("\n")[0].count("|") - 1
                        if md_cols != struct_cols and struct_cols > 1:
                            page_md = page_md.replace(md_table.rstrip("\n"), struct_table, 1)
                            table_improvements += 1

            # Insert page marker
            pages_md.append(f"<!-- page {page_num + 1} -->\n\n{page_md}")

        # Detect multi-column pages (before doc is closed)
        multi_col = _detect_multi_column(doc)
    finally:
        doc.close()

    md_text = "\n\n".join(pages_md)

    stats = {
        "page_markers": page_count,
        "table_improvements": table_improvements,
        "multi_column_pages": len(multi_col),
        "multi_column_details": multi_col,
    }

    return md_text, stats


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
    mode = stats.get("mode", "standard")
    print(f"\n--- Conversion Statistics ({mode}) ---")
    print(f"  Pages:    {stats['pages']}")
    print(f"  Words:    {stats['words']}")
    print(f"  Sections: {stats['sections']}")
    print(f"  Tables:   {stats['tables']}")
    if "figures" in stats:
        print(f"  Figures:  {stats['figures']}")
    if mode == "enhanced":
        print(f"  Page markers:      {stats.get('page_markers', 0)}")
        print(f"  Tables improved:   {stats.get('table_improvements', 0)}")
        print(f"  Multi-col pages:   {stats.get('multi_column_pages', 0)}")
    print("-----------------------------\n")


# ---------------------------------------------------------------------------
# Main conversion logic
# ---------------------------------------------------------------------------

def convert_pdf(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    do_extract_figures: bool = False,
    enhanced: bool = False,
) -> int:
    """Convert a PDF to Markdown + references JSON. Returns an exit code.

    When enhanced=True, uses page-by-page conversion with page markers,
    improved table extraction, and multi-column detection.
    """
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
    # 3. Convert PDF -> Markdown
    # ------------------------------------------------------------------
    enhanced_stats: dict = {}

    if enhanced:
        # Enhanced mode: page-by-page with markers + table improvement
        print(f"Converting (enhanced mode): {pdf_path}")
        try:
            md_text, enhanced_stats = _convert_page_by_page(pdf_path)
        except ImportError as exc:
            print(
                f"Error: required package not installed: {exc}\n"
                "Install with:  pip install pymupdf4llm",
                file=sys.stderr,
            )
            return EXIT_CONVERSION_ERROR
        except Exception as exc:
            print(f"Error during enhanced PDF conversion: {exc}", file=sys.stderr)
            return EXIT_CONVERSION_ERROR

        page_count = enhanced_stats.get("page_markers", 0)

        # Log multi-column detection
        if enhanced_stats.get("multi_column_pages", 0) > 0:
            print(f"\n  Multi-column layout detected on {enhanced_stats['multi_column_pages']} page(s):")
            for mc in enhanced_stats.get("multi_column_details", []):
                print(f"    Page {mc['page']}: {mc['columns']} columns")

        if enhanced_stats.get("table_improvements", 0) > 0:
            print(f"  Tables improved: {enhanced_stats['table_improvements']} table(s) replaced with structured extraction")
    else:
        # Standard mode: whole-document conversion
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
    # Collapse runs of 3+ blank lines into 2 (but preserve page markers)
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
    # 8. Write enhanced stats (if applicable)
    # ------------------------------------------------------------------
    if enhanced and enhanced_stats:
        enhanced_stats_path = output_dir / f"{stem}_enhanced_stats.json"
        try:
            enhanced_stats_path.write_text(
                json.dumps(enhanced_stats, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"Enhanced stats saved: {enhanced_stats_path}")
        except OSError:
            pass  # non-critical

    # ------------------------------------------------------------------
    # 9. Print statistics
    # ------------------------------------------------------------------
    stats = _compute_stats(md_text, page_count)
    stats["figures"] = len(figures)
    if enhanced:
        stats["mode"] = "enhanced"
        stats["page_markers"] = enhanced_stats.get("page_markers", 0)
        stats["table_improvements"] = enhanced_stats.get("table_improvements", 0)
        stats["multi_column_pages"] = enhanced_stats.get("multi_column_pages", 0)
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
    parser.add_argument(
        "--enhanced",
        action="store_true",
        default=False,
        help="Enable enhanced conversion: page markers, improved table extraction, multi-column detection.",
    )

    args = parser.parse_args()
    return convert_pdf(
        args.pdf,
        args.output_dir,
        do_extract_figures=args.extract_figures,
        enhanced=args.enhanced,
    )


if __name__ == "__main__":
    sys.exit(main())
