# Usage Guide

How to use refine-ink to review academic papers and interpret the output.

---

## Basic Usage

Inside Claude Code, with the project directory as your working directory:

```
/review path/to/paper.pdf
```

That single command launches the full 11-phase review pipeline (Phases 0--10). The system handles everything automatically: setup, conversion, chunking, parallel analysis, literature search, reference verification, cross-workflow synthesis (in triple-workflow mode), confidence iteration, synthesis, precision validation, and output generation.

For triple-workflow mode (three parallel analysis strategies for maximum coverage):

```
/review path/to/paper.pdf --triple
```

---

## What Happens During a Review

### Phase 0 -- Setup

The system creates a review directory under `reviews/`:

```
reviews/[paper_name]_[YYYY-MM-DD]/
  input/
  verification/
  chunks/
  agent_outputs/
  output/
```

The PDF is copied into `input/original.pdf`.

### Phase 1 -- PDF Conversion and Verification

The PDF is converted to Markdown using `pymupdf4llm`, which handles multi-column layouts, tables, equations, and footnotes. The conversion is then verified against the original PDF:

- **Word count comparison** (3% tolerance threshold)
- **Section/heading count** comparison
- **Table count** comparison
- **Reference count** comparison
- **Sentence-level spot checks** (20 random sentences, fuzzy matched)
- **First/last paragraph** presence check
- **Figure caption** preservation check
- **Footnote count** comparison

Results: **PASS** (proceed), **WARN** (proceed with caution, warnings shown), **FAIL** (stop and ask the user).

The system also detects:
- **Language**: English or Hungarian
- **Document type**: Article or PhD dissertation
- **Word count and page count**

### Phase 2 -- Chunking

The converted Markdown is split into chunks tailored to each analysis dimension. Different agents receive different chunk sizes (see [CHUNKING.md](CHUNKING.md) for rationale). A `chunk_map.json` is produced that maps each chunk to its assigned agents.

### Phase 3 -- Parallel Analysis

Seven analysis agents launch simultaneously:

1. **math-logic** -- equations, proofs, derivations
2. **notation** -- symbol/variable consistency
3. **exposition** -- argument flow and clarity
4. **empirical** -- tables/figures vs. text cross-checks
5. **cross-section** -- inter-section consistency
6. **econometrics** -- statistical methodology
7. **language** -- English quality and Hungarian register

Progress is reported as agents complete: "Phase 3: 5/7 dimensions complete."

### Phase 4 -- Literature Search

Using WebSearch (and Google Scholar via Chrome if available), the system searches for potentially missing key references. Results are compared against the paper's bibliography.

### Phase 5 -- Reference Verification

The extracted references are verified through a three-tier API cascade:

1. **CrossRef** -- DOI resolution and bibliographic search
2. **OpenAlex** -- broader coverage including books and working papers
3. **Semantic Scholar** -- strong coverage of social sciences

Each reference is classified as **Verified**, **Suspicious**, or **Unverifiable**. The references agent then interprets the results and flags hallucination patterns.

### Phase 6 -- Cross-Workflow Synthesis (triple-workflow mode only)

In triple-workflow mode, findings from all three workflows (A: markdown chunks, B: full PDF, C: PDF page-range chunks) are merged:

1. **Normalise locations** -- Map line numbers to page numbers using `<!-- page N -->` markers
2. **Group** findings by semantic similarity (same page ±1, same dimension, evidence overlap ≥ 0.7)
3. **Classify**: shared (2-3 workflows, confidence boosted), unique (re-verified), or contradicted (resolved against PDF)
4. **Deduplicate** into a single unified findings list
5. **Document provenance** in `agent_outputs/synthesis/dedup_map.json`

This phase is skipped in single-workflow mode.

### Phase 7 -- Confidence Iteration

All findings with confidence below 80% are sent to the **confidence-checker** (Opus model), which:

- Reads expanded context (500+ additional words around each finding)
- Re-evaluates with fresh eyes
- Checks for false positives
- Renders a verdict: **CONFIRM**, **REVISE**, or **WITHDRAW**

Findings that remain below 50% confidence after two iterations are moved to a Low-Confidence appendix.

### Phase 8 -- Synthesis

All validated findings are aggregated and written as a coherent referee report in academic prose. The report follows the structure of a top-journal referee report, not a bullet-point checklist.

### Phase 9 -- Precision Validation

The **precision-validator** (Opus model) re-checks every finding:

- **Tier A** (internal findings): 95% precision threshold, up to 3 iterations
- **Tier B** (external findings): 85--90% threshold, 15-minute time limit
- **Holistic check**: logical consistency, recommendation calibration, tone, internal contradictions, completeness

Findings that fail validation are downgraded to the Low-Confidence appendix.

### Phase 10 -- Output Generation

Final output is produced:

- `review_EN.md` and `review_EN.html` (English)
- `review_HU.md` and `review_HU.html` (Hungarian, if applicable)
- `manifest.json` (full audit trail)

A final summary is displayed:

```
Review complete.
Paper: [title]
Recommendation: [Accept/Minor Revisions/Major Revisions/Reject]
Findings: [N] critical, [N] major, [N] minor, [N] suggestions
References: [N] verified, [N] unverifiable, [N] suspicious
Average precision: [N]%
Time: [N] minutes
Output: reviews/[name]/output/review_EN.md (and .html)
```

---

## Understanding the Output

### Review Structure

The referee report is structured as follows:

| Section | Content |
|---|---|
| **Summary** | 1--2 paragraph overview of the paper's contribution |
| **Overall Assessment** | Strengths, concerns, recommendation |
| **Major Comments** | Numbered substantive paragraphs with verbatim corrections |
| **Minor Comments** | Numbered brief items with specific fixes |
| **Econometric/Statistical Methodology** | Dedicated methodology section |
| **Literature and References** | Coverage assessment + verification summary |
| **Language and Presentation** | Constructive language suggestions |
| **Suggestions for Improvement** | Optional enhancements |
| **Appendix A: Detailed Findings** | Table of all findings with severity and confidence |
| **Appendix B: Low-Confidence Findings** | Tentative observations that could not be fully validated |
| **Appendix C: Methodology Notes** | Technical notes on the review process |

### Severity Levels

| Level | Meaning | Typical Impact |
|---|---|---|
| **Critical** | Invalidates results, fundamental logical flaws, incorrect proofs | Reject or major revision |
| **Major** | Could change conclusions, significant methodology concerns | Major revision |
| **Minor** | Does not affect results: notation, clarity, presentation | Minor revision |
| **Suggestion** | Optional improvements, alternative approaches | No impact on recommendation |

### Confidence Scores

Every finding includes a confidence score from 0 to 100%:

| Range | Meaning |
|---|---|
| 90--100% | Clear, unambiguous error with direct evidence |
| 70--89% | Likely error, strong but not conclusive evidence |
| 50--69% | Possible issue, requires author clarification |
| Below 50% | Uncertain; appears in the Low-Confidence appendix only |

---

## Handling Warnings and Failures

### PDF Conversion Fails

If the conversion verification reports **FAIL**, the system will stop and show the failures. Common actions:

- Inspect the converted Markdown file manually for obvious issues
- Try a different PDF version of the paper (e.g., from the publisher vs. a preprint)
- For scanned PDFs, OCR the document first using an external tool

### PDF Conversion Warns

If the verification reports **WARN**, the system proceeds but displays warnings. Review the warnings to decide if they affect your use case. Common warnings include heading count mismatches (often due to PDF formatting quirks) and footnote count differences.

### References Cannot Be Verified

Unverifiable references are not necessarily errors. Common reasons:

- Working papers, dissertations, or books that are not indexed in academic databases
- Very recent publications not yet indexed
- Non-English publications with limited database coverage
- References with extraction errors (garbled authors or titles from PDF conversion)

The system flags truly suspicious references separately using hallucination detection patterns.

---

## Reviewing Hungarian Papers

The system automatically detects Hungarian-language papers based on linguistic markers and diacritics. When a Hungarian paper is detected:

1. All analysis is performed on the Hungarian text
2. **Two versions of the review are produced:**
   - `review_EN.md` / `review_EN.html` -- English version
   - `review_HU.md` / `review_HU.html` -- Hungarian version in proper academic register (tudományos stilus)
3. Language corrections use proper Hungarian academic conventions and terminology
4. The language agent checks Hungarian-specific issues: suffix/case usage, verb conjugation (definite vs. indefinite), sentence structure

---

## Reviewing PhD Dissertations

PhD dissertations (typically 100--200 pages) receive extended analysis:

- **Chapter-by-chapter analysis**: each chapter is treated as a semi-independent unit
- **Cross-chapter consistency**: the cross-section agent specifically checks for contradictions and thematic consistency between chapters
- **Coherence assessment**: the exposition agent evaluates whether the dissertation tells a coherent story across chapters
- **Extended processing time**: expect 60--90 minutes for a full dissertation review
- **Larger output**: the review will include chapter-specific sections in addition to the overall assessment

---

## Tips for Best Results

### PDF Quality

- Use the publisher's final PDF when available (cleaner formatting)
- Avoid scanned PDFs; the system works best with text-based documents
- Ensure the PDF has proper text encoding (copy-paste a sentence to verify)
- PDFs with standard academic formatting (single or double column) work best

### Paper Characteristics

- Papers with clearly marked sections (numbered headings) produce better chunking
- Papers with properly formatted reference lists (consistent style) yield better reference verification
- LaTeX-generated PDFs generally convert more reliably than Word-generated PDFs

### Workflow

- Start with a single paper to familiarise yourself with the output format
- Review the `manifest.json` to understand what the system did and how confident it is
- Check the agent outputs in `agent_outputs/` for detailed reasoning behind each finding
- Use the Low-Confidence appendix as a source of questions to explore, not as definitive findings

---

## Review Directory Contents

After a completed review, the directory contains:

| Path | Description |
|---|---|
| `input/original.pdf` | Copy of the input PDF |
| `input/[name]_converted.md` | Full Markdown conversion |
| `input/[name]_references.json` | Extracted reference entries (structured JSON) |
| `verification/[name]_verification.json` | Conversion verification report |
| `verification/reference_report.json` | Reference verification results per reference |
| `verification/validation_report.json` | Precision validation results per finding |
| `chunks/chunk_map.json` | Chunk boundaries and dimension assignments |
| `agent_outputs/math-logic.md` | Mathematical and logical correctness findings |
| `agent_outputs/notation.md` | Notation consistency findings + symbol inventory |
| `agent_outputs/exposition.md` | Argument flow and clarity findings |
| `agent_outputs/empirical.md` | Tables/figures vs. text cross-check findings |
| `agent_outputs/cross-section.md` | Inter-section consistency findings |
| `agent_outputs/econometrics.md` | Econometric methodology findings |
| `agent_outputs/literature.md` | Literature gap identification |
| `agent_outputs/references.md` | Reference validation and hallucination detection |
| `agent_outputs/language.md` | Language quality findings |
| `agent_outputs/confidence_check.md` | Confidence iteration results |
| `output/review_EN.md` | Final English review (Markdown) |
| `output/review_EN.html` | Final English review (styled HTML) |
| `output/review_HU.md` | Hungarian review, if applicable |
| `output/review_HU.html` | Hungarian review HTML, if applicable |
| `output/manifest.json` | Full audit trail |
