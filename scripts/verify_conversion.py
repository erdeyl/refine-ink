#!/usr/bin/env python3
"""
verify_conversion.py

Verifies content identity between a PDF and its Markdown conversion.

Usage:
    python verify_conversion.py input.pdf input_converted.md

Exit codes:
    0 - PASS (all checks passed)
    1 - WARN (non-critical differences detected)
    2 - FAIL (critical content loss detected)

Dependencies:
    pymupdf (fitz) for PDF text extraction; standard library for everything else.
"""

import argparse
import difflib
import json
import os
import random
import re
import sys
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    fitz = None


def _require_fitz() -> None:
    if fitz is None:
        raise RuntimeError("pymupdf is required. Install with: pip install pymupdf")


# ---------------------------------------------------------------------------
# PDF extraction helpers
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: str) -> str:
    """Return the full plain-text content of a PDF, page by page."""
    _require_fitz()
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return "\n".join(pages)


def extract_pdf_blocks(pdf_path: str) -> list[dict]:
    """Return per-page block-level data (text, fonts, sizes) for heuristic analysis."""
    _require_fitz()
    doc = fitz.open(pdf_path)
    blocks = []
    for page_num, page in enumerate(doc):
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:  # text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        blocks.append({
                            "page": page_num,
                            "text": span.get("text", ""),
                            "size": span.get("size", 0),
                            "flags": span.get("flags", 0),  # bold=16, italic=2
                            "font": span.get("font", ""),
                            "bbox": span.get("bbox", []),
                        })
    doc.close()
    return blocks


# ---------------------------------------------------------------------------
# Tokenisation / normalisation
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-z0-9\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF''-]+")


def tokenize(text: str) -> list[str]:
    """Split text into word tokens (Unicode-aware)."""
    return _WORD_RE.findall(text)


def normalize(text: str) -> str:
    """Lower-case, collapse whitespace, strip non-alphanumeric for comparison."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Metric extraction: PDF
# ---------------------------------------------------------------------------

def _median_body_size(blocks: list[dict]) -> float:
    """Estimate the most common (body) font size from span data."""
    sizes = [b["size"] for b in blocks if b["text"].strip()]
    if not sizes:
        return 12.0
    # Use a simple frequency count
    freq: dict[float, int] = {}
    for s in sizes:
        rounded = round(s, 1)
        freq[rounded] = freq.get(rounded, 0) + 1
    return max(freq, key=freq.get)


def pdf_headings(blocks: list[dict]) -> list[str]:
    """Heuristically detect headings: spans larger than body text or bold."""
    body_size = _median_body_size(blocks)
    threshold = body_size + 0.5  # anything noticeably larger is a heading

    headings: list[str] = []
    prev_text = ""
    for b in blocks:
        txt = b["text"].strip()
        if not txt:
            continue
        is_bold = bool(b["flags"] & 16)
        is_large = b["size"] >= threshold
        # Numbered section pattern (e.g. "1. Introduction", "2.3 Methods")
        is_numbered_section = bool(re.match(r"^\d+(\.\d+)*\s", txt))

        if (is_large or (is_bold and is_numbered_section)) and len(txt) < 200:
            # Avoid duplicate consecutive headings from multi-span lines
            if txt != prev_text:
                headings.append(txt)
                prev_text = txt
    return headings


def pdf_tables(pdf_path: str) -> int:
    """Count tables in the PDF using pymupdf's built-in table finder."""
    _require_fitz()
    doc = fitz.open(pdf_path)
    count = 0
    for page in doc:
        try:
            tables = page.find_tables()
            count += len(tables.tables)
        except Exception:
            pass
    doc.close()
    return count


def pdf_references(text: str) -> int:
    """Count reference entries in the PDF text.

    Looks for a References/Bibliography section and counts numbered or
    author-year entries.
    """
    # Find the references section
    ref_match = re.search(
        r"\b(References|Bibliography|Works\s+Cited)\b",
        text,
        re.IGNORECASE,
    )
    if not ref_match:
        return 0

    ref_text = text[ref_match.end():]

    # Strategy 1: numbered references like [1], [2], ...
    numbered = re.findall(r"^\s*\[(\d+)\]", ref_text, re.MULTILINE)
    if len(numbered) >= 3:
        return len(numbered)

    # Strategy 2: entries starting with author names (capitalized word followed
    # by comma or period, typical of APA / Chicago)
    entries = re.findall(
        r"(?:^|\n)\s*[A-Z][a-z]+[\s,].*?\(\d{4}\)",
        ref_text,
    )
    if len(entries) >= 3:
        return len(entries)

    # Strategy 3: count non-empty lines as rough proxy
    lines = [l.strip() for l in ref_text.split("\n") if l.strip()]
    # Stop at next major heading-like line (all caps, short)
    filtered: list[str] = []
    for line in lines:
        if len(line) < 50 and line == line.upper() and len(line.split()) <= 5:
            break
        filtered.append(line)
    return len(filtered)


def pdf_figure_captions(text: str) -> list[str]:
    """Extract figure captions from PDF text."""
    captions = re.findall(
        r"((?:Figure|Fig\.?)\s*\d+[.:]\s*.+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    return [c.strip() for c in captions]


def pdf_footnotes(text: str) -> int:
    """Estimate footnote count in PDF text."""
    # Superscript numbers at start of line in footnote areas
    footnotes = re.findall(r"(?:^|\n)\s*(\d{1,3})\s+[A-Z]", text)
    # Also look for markers like * or daggers
    symbol_notes = re.findall(r"(?:^|\n)\s*[*\u2020\u2021\u00a7]\s+\S", text)
    return max(len(footnotes), len(symbol_notes))


def pdf_footnotes_from_blocks(blocks: list[dict], body_size: float) -> int:
    """Count footnotes using font-size heuristic (smaller than body text)."""
    footnote_size_threshold = body_size - 1.5
    if footnote_size_threshold < 5:
        return 0

    footnote_texts: list[str] = []
    current = ""
    in_footnote_zone = False
    for b in blocks:
        txt = b["text"].strip()
        if not txt:
            continue
        if b["size"] <= footnote_size_threshold and b["size"] >= 5:
            if re.match(r"^\d{1,3}\s", txt) or re.match(r"^[*\u2020\u2021]\s", txt):
                if current:
                    footnote_texts.append(current)
                current = txt
                in_footnote_zone = True
            elif in_footnote_zone:
                current += " " + txt
        else:
            if current:
                footnote_texts.append(current)
                current = ""
            in_footnote_zone = False
    if current:
        footnote_texts.append(current)
    return len(footnote_texts)


# ---------------------------------------------------------------------------
# Metric extraction: Markdown
# ---------------------------------------------------------------------------

def md_headings(md_text: str) -> list[str]:
    """Extract top-level to subsection headings from Markdown."""
    matches = list(re.finditer(r"^(#{1,3})\s+(.+)$", md_text, re.MULTILINE))
    headings: list[str] = []
    for idx, m in enumerate(matches):
        level = len(m.group(1))
        heading = m.group(2).strip()
        # Exclude a likely document title H1 from section-count comparisons.
        if idx == 0 and level == 1 and not re.match(r"^\d+(\.\d+)*\s", heading):
            continue
        headings.append(heading)
    return headings


def md_tables(md_text: str) -> int:
    """Count Markdown table blocks (contiguous lines with | delimiters)."""
    count = 0
    in_table = False
    for line in md_text.split("\n"):
        stripped = line.strip()
        if "|" in stripped and (
            stripped.startswith("|") or re.match(r".+\|.+", stripped)
        ):
            if not in_table:
                count += 1
                in_table = True
        else:
            in_table = False
    return count


def md_references(md_text: str) -> int:
    """Count reference entries in Markdown."""
    ref_match = re.search(
        r"^#{1,3}\s*(References|Bibliography|Works\s+Cited)",
        md_text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not ref_match:
        return 0

    ref_text = md_text[ref_match.end():]

    # Stop at next heading
    next_heading = re.search(r"^#{1,3}\s+", ref_text, re.MULTILINE)
    if next_heading:
        ref_text = ref_text[: next_heading.start()]

    # Numbered references
    numbered = re.findall(r"^\s*\[?\d+\]?[.\)]\s", ref_text, re.MULTILINE)
    if len(numbered) >= 3:
        return len(numbered)

    # List items
    list_items = re.findall(r"^\s*[-*]\s+", ref_text, re.MULTILINE)
    if len(list_items) >= 3:
        return len(list_items)

    # Non-empty lines
    lines = [l.strip() for l in ref_text.split("\n") if l.strip()]
    return len(lines)


def md_figure_captions(md_text: str) -> list[str]:
    """Extract figure captions from Markdown."""
    # Markdown image captions: ![caption](url) or **Figure N:** text
    captions: list[str] = []
    img_caps = re.findall(r"!\[([^\]]+)\]", md_text)
    captions.extend(c.strip() for c in img_caps if c.strip())

    bold_caps = re.findall(
        r"\*\*(?:Figure|Fig\.?)\s*\d+[.:]\*\*\s*(.+?)(?:\n|$)",
        md_text,
        re.IGNORECASE,
    )
    captions.extend(c.strip() for c in bold_caps)

    plain_caps = re.findall(
        r"(?:^|\n)\s*(?:Figure|Fig\.?)\s*\d+[.:]\s*(.+?)(?:\n|$)",
        md_text,
        re.IGNORECASE,
    )
    captions.extend(c.strip() for c in plain_caps)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in captions:
        norm = normalize(c)
        if norm not in seen:
            seen.add(norm)
            unique.append(c)
    return unique


def md_footnotes(md_text: str) -> int:
    """Count Markdown footnotes ([^N]: ... patterns)."""
    return len(re.findall(r"^\s*\[\^\d+\]:", md_text, re.MULTILINE))


# ---------------------------------------------------------------------------
# Sentence extraction and spot-checking
# ---------------------------------------------------------------------------

def extract_sentences(text: str, min_words: int = 10) -> list[str]:
    """Extract sentences with at least *min_words* words from *text*."""
    # Rough sentence splitting
    raw = re.split(r"(?<=[.!?])\s+", text)
    sentences: list[str] = []
    for s in raw:
        s = s.strip()
        words = tokenize(s)
        if len(words) >= min_words:
            sentences.append(s)
    return sentences


def fuzzy_match(needle: str, haystack: str, threshold: float = 0.85) -> bool:
    """Return True if *needle* has a fuzzy match inside *haystack*."""
    needle_norm = normalize(needle)
    haystack_norm = normalize(haystack)

    if needle_norm in haystack_norm:
        return True

    # Sliding window comparison for efficiency on large haystacks
    needle_words = needle_norm.split()
    haystack_words = haystack_norm.split()
    window = len(needle_words)

    if window == 0:
        return True
    if len(haystack_words) < window:
        return difflib.SequenceMatcher(
            None, needle_norm, haystack_norm
        ).ratio() >= threshold

    best = 0.0
    # To avoid O(n*m) on very large texts, sample positions around keyword hits
    # First, try to find a neighbourhood using first few words of needle
    search_key = " ".join(needle_words[:3])
    positions: list[int] = []
    start = 0
    while True:
        idx = haystack_norm.find(search_key, start)
        if idx == -1:
            break
        # Convert char position to approximate word position
        word_pos = len(haystack_norm[:idx].split())
        positions.append(max(0, word_pos - 2))
        start = idx + 1

    # If no keyword hits, fall back to sampling
    if not positions:
        step = max(1, len(haystack_words) // 200)
        positions = list(range(0, len(haystack_words) - window + 1, step))

    for i in positions:
        chunk = " ".join(haystack_words[i : i + window + 5])
        ratio = difflib.SequenceMatcher(None, needle_norm, chunk).ratio()
        if ratio >= threshold:
            return True
        best = max(best, ratio)

    return False


# ---------------------------------------------------------------------------
# Paragraph extraction for first/last check
# ---------------------------------------------------------------------------

def extract_paragraphs(text: str) -> list[str]:
    """Return a list of non-trivial paragraphs (>20 chars)."""
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if len(p.strip()) > 20]


def first_meaningful_paragraph(text: str) -> str:
    """Return the first paragraph with substantial content."""
    paras = extract_paragraphs(text)
    for p in paras:
        words = tokenize(p)
        if len(words) >= 5:
            return p
    return ""


def last_paragraph_before_references(text: str) -> str:
    """Return the last substantial paragraph before a References section."""
    ref_match = re.search(
        r"\b(References|Bibliography|Works\s+Cited)\b",
        text,
        re.IGNORECASE,
    )
    body = text[: ref_match.start()] if ref_match else text
    paras = extract_paragraphs(body)
    for p in reversed(paras):
        words = tokenize(p)
        if len(words) >= 5:
            return p
    return ""


# ---------------------------------------------------------------------------
# Main verification logic
# ---------------------------------------------------------------------------

def verify(pdf_path: str, md_path: str) -> dict:
    """Run all checks and return the JSON-serialisable report dict."""
    _require_fitz()

    warnings: list[str] = []
    failures: list[str] = []

    # --- Load sources ---
    pdf_text = extract_pdf_text(pdf_path)
    blocks = extract_pdf_blocks(pdf_path)
    body_size = _median_body_size(blocks)

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # --- 1. Word count comparison ---
    pdf_words = tokenize(pdf_text)
    md_words = tokenize(md_text)
    pdf_wc = len(pdf_words)
    md_wc = len(md_words)
    wc_diff_pct = abs(pdf_wc - md_wc) / max(pdf_wc, 1) * 100

    if wc_diff_pct > 3:
        failures.append(
            f"Word count difference {wc_diff_pct:.1f}% exceeds 3% threshold "
            f"(PDF: {pdf_wc}, MD: {md_wc})"
        )

    # --- 2. Section/heading count ---
    sections_pdf_list = pdf_headings(blocks)
    sections_md_list = md_headings(md_text)
    sections_pdf_count = len(sections_pdf_list)
    sections_md_count = len(sections_md_list)

    if sections_pdf_count != sections_md_count:
        warnings.append(
            f"Heading count differs: PDF={sections_pdf_count}, MD={sections_md_count}"
        )

    # --- 3. Table count ---
    tables_pdf_count = pdf_tables(pdf_path)
    tables_md_count = md_tables(md_text)

    if tables_pdf_count > 0 and tables_md_count < tables_pdf_count:
        failures.append(
            f"Tables missing: PDF has {tables_pdf_count}, MD has {tables_md_count}"
        )
    elif tables_pdf_count != tables_md_count:
        warnings.append(
            f"Table count differs: PDF={tables_pdf_count}, MD={tables_md_count}"
        )

    # --- 4. Reference count ---
    refs_pdf_count = pdf_references(pdf_text)
    refs_md_count = md_references(md_text)

    if refs_pdf_count != refs_md_count:
        warnings.append(
            f"Reference count differs: PDF={refs_pdf_count}, MD={refs_md_count}"
        )

    # --- 5. Sentence-level spot checks ---
    pdf_sentences = extract_sentences(pdf_text, min_words=10)
    spot_total = 20
    if len(pdf_sentences) < spot_total:
        sample = pdf_sentences
        spot_total = len(sample)
    else:
        random.seed(42)  # reproducibility
        sample = random.sample(pdf_sentences, spot_total)

    spot_hits = 0
    missed_sentences: list[str] = []
    for sent in sample:
        if fuzzy_match(sent, md_text, threshold=0.85):
            spot_hits += 1
        else:
            missed_sentences.append(sent[:120])

    if spot_total > 0 and (spot_total - spot_hits) > 2:
        failures.append(
            f"Spot check: only {spot_hits}/{spot_total} sentences found in MD. "
            f"Missing examples: {missed_sentences[:3]}"
        )

    # --- 6. First/last content check ---
    pdf_first = first_meaningful_paragraph(pdf_text)
    pdf_last = last_paragraph_before_references(pdf_text)

    if pdf_first and not fuzzy_match(pdf_first[:200], md_text, threshold=0.80):
        failures.append("First meaningful paragraph from PDF not found in Markdown")

    if pdf_last and not fuzzy_match(pdf_last[:200], md_text, threshold=0.80):
        failures.append("Last paragraph before references from PDF not found in Markdown")

    # --- 7. Figure caption check ---
    fig_caps_pdf = pdf_figure_captions(pdf_text)
    fig_caps_md = md_figure_captions(md_text)
    missing_captions: list[str] = []

    for cap in fig_caps_pdf:
        cap_short = cap[:100]
        if not fuzzy_match(cap_short, md_text, threshold=0.80):
            missing_captions.append(cap_short)

    if missing_captions:
        warnings.append(
            f"Figure captions missing from MD: {missing_captions}"
        )

    # --- 8. Footnote count ---
    fn_pdf_text = pdf_footnotes(pdf_text)
    fn_pdf_blocks = pdf_footnotes_from_blocks(blocks, body_size)
    fn_pdf = max(fn_pdf_text, fn_pdf_blocks)
    fn_md = md_footnotes(md_text)

    if fn_pdf > 0:
        fn_diff_pct = abs(fn_pdf - fn_md) / max(fn_pdf, 1) * 100
        if fn_diff_pct > 10:
            warnings.append(
                f"Footnote count differs by {fn_diff_pct:.0f}%: "
                f"PDF~{fn_pdf}, MD={fn_md}"
            )

    # --- Determine overall status ---
    if failures:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    report = {
        "status": status,
        "pdf_word_count": pdf_wc,
        "md_word_count": md_wc,
        "word_count_diff_pct": round(wc_diff_pct, 2),
        "sections_pdf": sections_pdf_count,
        "sections_md": sections_md_count,
        "tables_pdf": tables_pdf_count,
        "tables_md": tables_md_count,
        "references_pdf": refs_pdf_count,
        "references_md": refs_md_count,
        "spot_check_hits": spot_hits,
        "spot_check_total": spot_total,
        "figure_captions_pdf": len(fig_caps_pdf),
        "figure_captions_md": len(fig_caps_md),
        "footnotes_pdf": fn_pdf,
        "footnotes_md": fn_md,
        "warnings": warnings,
        "failures": failures,
    }

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify content identity between a PDF and its Markdown conversion.",
    )
    parser.add_argument("pdf", help="Path to the original PDF file")
    parser.add_argument("md", help="Path to the converted Markdown file")
    args = parser.parse_args()

    try:
        _require_fitz()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    pdf_path = os.path.abspath(args.pdf)
    md_path = os.path.abspath(args.md)

    if not os.path.isfile(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(md_path):
        print(f"Error: Markdown file not found: {md_path}", file=sys.stderr)
        sys.exit(2)

    report = verify(pdf_path, md_path)

    # Output JSON to stdout
    report_json = json.dumps(report, indent=2, ensure_ascii=False)
    print(report_json)

    # Save report next to the PDF
    pdf_stem = Path(pdf_path).stem
    pdf_dir = Path(pdf_path).parent
    report_path = pdf_dir / f"{pdf_stem}_verification.json"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_json)
        f.write("\n")
    print(f"\nReport saved to: {report_path}", file=sys.stderr)

    # Exit code
    if report["status"] == "FAIL":
        sys.exit(2)
    elif report["status"] == "WARN":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
