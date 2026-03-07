#!/usr/bin/env python3
"""
pdf_section_map.py - Map PDF section headings to page ranges.

Detects section/heading boundaries in a PDF using font-size and bold
heuristics, and maps them to page ranges for direct-PDF review agents.
Produces a JSON section map analogous to chunk_map.json but using page
ranges instead of line ranges.

Usage:
    python pdf_section_map.py input.pdf [--output pdf_section_map.json]

Dependencies:
    pymupdf (fitz) for PDF analysis.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import pymupdf  # type: ignore
except ImportError:
    pymupdf = None


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_DEPENDENCY_ERROR = 2
EXIT_IO_ERROR = 3


# ---------------------------------------------------------------------------
# PDF analysis helpers
# ---------------------------------------------------------------------------

def _mode_body_size(blocks: list[dict]) -> float:
    """Estimate the most common (mode) body font size from span data."""
    sizes = [b["size"] for b in blocks if b["text"].strip()]
    if not sizes:
        return 12.0
    freq: dict[float, int] = {}
    for s in sizes:
        rounded = round(s, 1)
        freq[rounded] = freq.get(rounded, 0) + 1
    return max(freq, key=freq.get)


def _extract_blocks(pdf_path: str) -> list[dict]:
    """Extract per-span block data from the PDF."""
    doc = pymupdf.open(pdf_path)
    blocks = []
    try:
        for page_num, page in enumerate(doc):
            page_dict = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:  # text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            blocks.append({
                                "page": page_num + 1,  # 1-indexed
                                "text": span.get("text", ""),
                                "size": span.get("size", 0),
                                "flags": span.get("flags", 0),
                                "font": span.get("font", ""),
                                "bbox": span.get("bbox", []),
                            })
    finally:
        doc.close()
    return blocks


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

def detect_headings(pdf_path: str) -> list[dict]:
    """Detect section headings in the PDF using font-size and bold heuristics.

    Returns a list of dicts:
        {text, page, font_size, is_bold, level}
    where level is inferred (1=section, 2=subsection, 3=sub-sub).
    """
    blocks = _extract_blocks(pdf_path)
    body_size = _mode_body_size(blocks)
    threshold = body_size + 0.5

    raw_headings: list[dict] = []
    prev_text = ""

    for b in blocks:
        txt = b["text"].strip()
        if not txt or len(txt) > 200:
            continue

        is_bold = bool(b["flags"] & 16)
        is_large = b["size"] >= threshold
        is_numbered = bool(re.match(r"^\d+(\.\d+)*\.?\s", txt))

        if is_large or (is_bold and is_numbered):
            if txt != prev_text:
                raw_headings.append({
                    "text": txt,
                    "page": b["page"],
                    "font_size": round(b["size"], 1),
                    "is_bold": is_bold,
                })
                prev_text = txt

    # Fallback: if too few headings found, try numbered-section regex on all blocks
    if len(raw_headings) < 3:
        prev_text = ""
        for b in blocks:
            txt = b["text"].strip()
            if not txt or len(txt) > 200:
                continue
            if re.match(r"^\d+(\.\d+)*\.?\s+[A-Z]", txt) and len(txt) < 100:
                if txt != prev_text:
                    raw_headings.append({
                        "text": txt,
                        "page": b["page"],
                        "font_size": round(b["size"], 1),
                        "is_bold": bool(b["flags"] & 16),
                    })
                    prev_text = txt

    # Deduplicate by text (keep first occurrence)
    seen: set[str] = set()
    unique: list[dict] = []
    for h in raw_headings:
        norm = h["text"].lower().strip()
        if norm not in seen:
            seen.add(norm)
            unique.append(h)

    # Infer heading levels from font size tiers
    if unique:
        sizes = sorted(set(h["font_size"] for h in unique), reverse=True)
        size_to_level = {s: i + 1 for i, s in enumerate(sizes[:3])}
        for h in unique:
            h["level"] = size_to_level.get(h["font_size"], min(3, len(sizes)))

    return unique


# ---------------------------------------------------------------------------
# Page content detection
# ---------------------------------------------------------------------------

def detect_page_content(doc, page_num: int) -> dict:
    """Detect content types on a specific page (1-indexed).

    Args:
        doc: An open pymupdf document.
        page_num: 1-indexed page number.

    Returns: {has_tables, has_figures, has_equations}
    """
    page = doc[page_num - 1]  # 0-indexed in pymupdf

    # Tables
    has_tables = False
    try:
        tables = page.find_tables()
        has_tables = len(tables.tables) > 0
    except Exception:
        pass

    # Figures (embedded images above minimum size)
    has_figures = False
    try:
        images = page.get_images(full=True)
        for img_info in images:
            try:
                base_image = doc.extract_image(img_info[0])
                w = base_image.get("width", 0)
                h = base_image.get("height", 0)
                if w >= 150 and h >= 100:
                    has_figures = True
                    break
            except Exception:
                pass
    except Exception:
        pass

    # Equations (heuristic: look for math-like patterns in text)
    has_equations = False
    text = page.get_text("text")
    equation_patterns = [
        r"[\u2200-\u22FF]",           # Mathematical operators
        r"[\u0391-\u03C9]",           # Greek letters
        r"\$[^$]+\$",                 # LaTeX inline math
        r"\\\(.*?\\\)",               # LaTeX delimited math
        r"∑|∏|∫|∂|∇|√|±|≤|≥|≠|→|∞",  # Common math symbols
    ]
    for pattern in equation_patterns:
        if re.search(pattern, text):
            has_equations = True
            break

    return {
        "has_tables": has_tables,
        "has_figures": has_figures,
        "has_equations": has_equations,
    }


# ---------------------------------------------------------------------------
# Section map construction
# ---------------------------------------------------------------------------

def build_section_map(
    headings: list[dict],
    total_pages: int,
    doc,
    min_section_pages: int = 1,
) -> dict:
    """Build a section map from detected headings.

    Args:
        headings: List of detected heading dicts.
        total_pages: Total page count.
        doc: An open pymupdf document (used for content detection).
        min_section_pages: Minimum pages per section before merging.

    Returns a dict with:
        total_pages, sections[], dimension_assignments{}
    """
    sections: list[dict] = []

    if not headings:
        # No headings detected — treat entire document as one section
        content = detect_page_content(doc, 1)
        sections.append({
            "id": "s1",
            "heading": "Full Document",
            "start_page": 1,
            "end_page": total_pages,
            "pages": total_pages,
            "level": 1,
            "has_tables": content["has_tables"],
            "has_figures": content["has_figures"],
            "has_equations": content["has_equations"],
            "is_references": False,
            "is_abstract": False,
        })
    else:
        for i, heading in enumerate(headings):
            start_page = heading["page"]
            if i + 1 < len(headings):
                # End at the page before the next heading starts
                # (or same page if next heading is on same page)
                next_start = headings[i + 1]["page"]
                end_page = max(start_page, next_start - 1) if next_start > start_page else start_page
            else:
                end_page = total_pages

            heading_lower = heading["text"].lower().strip()
            is_references = bool(re.search(
                r"(references|bibliography|works\s+cited|literature\s+cited)",
                heading_lower,
            ))
            is_abstract = "abstract" in heading_lower

            # Detect content for the section (sample first page)
            content = detect_page_content(doc, start_page)

            sections.append({
                "id": f"s{i + 1}",
                "heading": heading["text"],
                "start_page": start_page,
                "end_page": end_page,
                "pages": end_page - start_page + 1,
                "level": heading.get("level", 1),
                "has_tables": content["has_tables"],
                "has_figures": content["has_figures"],
                "has_equations": content["has_equations"],
                "is_references": is_references,
                "is_abstract": is_abstract,
            })

    # Merge very small sections with their neighbors
    if min_section_pages > 1:
        merged: list[dict] = []
        for s in sections:
            if merged and s["pages"] < min_section_pages and not s["is_references"]:
                # Merge into previous section
                prev = merged[-1]
                prev["end_page"] = s["end_page"]
                prev["pages"] = prev["end_page"] - prev["start_page"] + 1
                prev["heading"] += f" + {s['heading']}"
                prev["has_tables"] = prev["has_tables"] or s["has_tables"]
                prev["has_figures"] = prev["has_figures"] or s["has_figures"]
                prev["has_equations"] = prev["has_equations"] or s["has_equations"]
            else:
                merged.append(s)
        sections = merged
        # Re-number IDs
        for i, s in enumerate(sections):
            s["id"] = f"s{i + 1}"

    # Build dimension assignments
    assignments = assign_dimensions(sections)

    return {
        "total_pages": total_pages,
        "sections": sections,
        "dimension_assignments": assignments,
    }


# ---------------------------------------------------------------------------
# Dimension assignment
# ---------------------------------------------------------------------------

def _pages_str(start: int, end: int) -> str:
    """Format a page range for the Read tool's pages parameter."""
    if start == end:
        return str(start)
    return f"{start}-{end}"


def _group_sections(
    sections: list[dict],
    target_pages: int,
    filter_fn=None,
) -> list[dict]:
    """Group sections into chunks of approximately target_pages pages.

    Returns list of {sections: [ids], pages: "start-end"} dicts.
    """
    eligible = [s for s in sections if (filter_fn is None or filter_fn(s))]
    if not eligible:
        return []

    groups: list[dict] = []
    current_ids: list[str] = []
    current_start = 0
    current_end = 0
    current_pages = 0

    for s in eligible:
        if current_pages > 0 and current_pages + s["pages"] > target_pages * 1.5:
            # Flush current group
            groups.append({
                "sections": current_ids,
                "pages": _pages_str(current_start, current_end),
            })
            current_ids = [s["id"]]
            current_start = s["start_page"]
            current_end = s["end_page"]
            current_pages = s["pages"]
        else:
            current_ids.append(s["id"])
            if not current_start:
                current_start = s["start_page"]
            current_end = s["end_page"]
            current_pages += s["pages"]

    if current_ids:
        groups.append({
            "sections": current_ids,
            "pages": _pages_str(current_start, current_end),
        })

    return groups


def assign_dimensions(sections: list[dict]) -> dict:
    """Assign sections to agent dimensions based on content and chunk size targets."""
    non_ref = [s for s in sections if not s["is_references"]]
    ref_sections = [s for s in sections if s["is_references"]]

    assignments: dict[str, list[dict]] = {}

    # math-logic: sections with equations, ~3-4 pages per group
    eq_sections = [s for s in non_ref if s["has_equations"]]
    if eq_sections:
        assignments["math-logic"] = _group_sections(eq_sections, target_pages=4)

    # notation: all non-reference sections, ~4-5 pages per group
    assignments["notation"] = _group_sections(non_ref, target_pages=5)

    # exposition: all non-reference sections, ~5-6 pages per group
    assignments["exposition"] = _group_sections(non_ref, target_pages=6)

    # empirical: sections with tables/figures, ~4-5 pages per group
    emp_sections = [s for s in non_ref if s["has_tables"] or s["has_figures"]]
    if emp_sections:
        assignments["empirical"] = _group_sections(emp_sections, target_pages=5)
    else:
        # If no tables/figures detected, assign all non-ref sections
        assignments["empirical"] = _group_sections(non_ref, target_pages=5)

    # cross-section: pairs of related sections (abstract+conclusion, intro+results, methods+results)
    cross_pairs = _build_cross_section_pairs(non_ref)
    if cross_pairs:
        assignments["cross-section"] = cross_pairs

    # econometrics: all non-reference sections, ~5 pages per group
    assignments["econometrics"] = _group_sections(non_ref, target_pages=5)

    # language: all non-reference sections, ~5-6 pages per group
    assignments["language"] = _group_sections(non_ref, target_pages=6)

    # references: reference sections as a single group
    if ref_sections:
        start = ref_sections[0]["start_page"]
        end = ref_sections[-1]["end_page"]
        assignments["references"] = [{
            "sections": [s["id"] for s in ref_sections],
            "pages": _pages_str(start, end),
        }]

    return assignments


def _build_cross_section_pairs(sections: list[dict]) -> list[dict]:
    """Build cross-section analysis pairs from section headings."""
    pairs: list[dict] = []

    def find_section(keyword: str) -> Optional[dict]:
        for s in sections:
            if keyword in s["heading"].lower():
                return s
        return None

    # Abstract + Conclusion
    abstract = find_section("abstract")
    conclusion = find_section("conclu")
    if abstract and conclusion:
        pages_list = []
        if abstract["start_page"] == conclusion["start_page"]:
            pages_list.append(_pages_str(abstract["start_page"], conclusion["end_page"]))
        else:
            pages_list.append(_pages_str(abstract["start_page"], abstract["end_page"]))
            pages_list.append(_pages_str(conclusion["start_page"], conclusion["end_page"]))
        pairs.append({
            "sections": [abstract["id"], conclusion["id"]],
            "pages": ",".join(pages_list),
            "pair_type": "abstract_conclusion",
        })

    # Introduction + Results/Discussion
    intro = find_section("introduction") or find_section("intro")
    results = find_section("result") or find_section("discussion") or find_section("finding")
    if intro and results:
        pages_list = []
        pages_list.append(_pages_str(intro["start_page"], intro["end_page"]))
        pages_list.append(_pages_str(results["start_page"], results["end_page"]))
        pairs.append({
            "sections": [intro["id"], results["id"]],
            "pages": ",".join(pages_list),
            "pair_type": "intro_results",
        })

    # Methods + Results
    methods = find_section("method") or find_section("material") or find_section("data")
    if methods and results and methods != results:
        pages_list = []
        pages_list.append(_pages_str(methods["start_page"], methods["end_page"]))
        pages_list.append(_pages_str(results["start_page"], results["end_page"]))
        pairs.append({
            "sections": [methods["id"], results["id"]],
            "pages": ",".join(pages_list),
            "pair_type": "methods_results",
        })

    # If no pairs could be built, create sequential pairs of all sections
    if not pairs and len(sections) >= 2:
        for i in range(0, len(sections) - 1, 2):
            s1 = sections[i]
            s2 = sections[i + 1]
            pairs.append({
                "sections": [s1["id"], s2["id"]],
                "pages": _pages_str(s1["start_page"], s2["end_page"]),
                "pair_type": "sequential",
            })

    return pairs


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map PDF section headings to page ranges for direct-PDF review agents.",
    )
    parser.add_argument(
        "pdf",
        type=Path,
        help="Path to the input PDF file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: pdf_section_map.json in same directory as PDF).",
    )
    parser.add_argument(
        "--min-section-pages",
        type=int,
        default=1,
        help="Minimum pages for a section; smaller sections are merged with neighbors (default: 1).",
    )

    args = parser.parse_args()

    if pymupdf is None:
        print(
            "Error: missing dependency 'pymupdf' (fitz). Install with: pip install pymupdf",
            file=sys.stderr,
        )
        return EXIT_DEPENDENCY_ERROR

    pdf_path = args.pdf
    if not pdf_path.is_file():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if pdf_path.suffix.lower() != ".pdf":
        print(f"Error: not a PDF file: {pdf_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    # Detect headings
    print(f"Analyzing: {pdf_path}")
    headings = detect_headings(str(pdf_path))
    print(f"Headings detected: {len(headings)}")
    for h in headings:
        print(f"  p.{h['page']}: [{h.get('level', '?')}] {h['text']}")

    # Open PDF once for content detection and section mapping
    doc = pymupdf.open(str(pdf_path))
    try:
        total_pages = doc.page_count

        # Build section map
        section_map = build_section_map(
            headings,
            total_pages,
            doc,
            min_section_pages=args.min_section_pages,
        )
    finally:
        doc.close()

    # Determine output path
    output_path = args.output
    if output_path is None:
        output_path = pdf_path.parent / "pdf_section_map.json"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    try:
        output_path.write_text(
            json.dumps(section_map, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nSection map saved: {output_path}")
        print(f"  Total pages: {total_pages}")
        print(f"  Sections: {len(section_map['sections'])}")
        print(f"  Dimensions assigned: {list(section_map['dimension_assignments'].keys())}")
    except OSError as exc:
        print(f"Error writing output: {exc}", file=sys.stderr)
        return EXIT_IO_ERROR

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
