# Chunking Strategy

This document explains why and how refine-ink splits papers into chunks for analysis, including the dimension-specific chunk sizes, the rationale behind each, and the overlap and adaptive sizing strategies.

---

## Why Chunk?

Large language models have finite context windows and, more importantly, finite *attention budgets*. Even when a model can technically ingest an entire paper in one pass, the quality of its analysis degrades for several reasons:

1. **Attention dilution** -- In a single pass over a 12,000-word paper, each token competes for attention with every other token. Important details (a sign error in Equation 7, a transposition in Table 3) are easily missed.

2. **Focus** -- When an agent is given a 1,000-word chunk and asked to check every equation, it can devote its full capacity to those equations. When given 12,000 words, it tends to skim.

3. **Thoroughness** -- Empirically, chunked analysis produces more findings per page than whole-document analysis, and those findings are more precise (higher confidence scores, better-located evidence).

4. **Parallelism** -- Chunking enables multiple agents to work simultaneously on different parts of the paper, significantly reducing wall-clock time.

The tradeoff is that chunked analysis can miss issues that only become apparent when reading two distant sections together. This is why the **cross-section** agent exists: it specifically analyses *pairs* of related sections to catch inter-section inconsistencies.

---

## Dimension-Specific Chunk Sizes

Different review dimensions benefit from different amounts of context. The chunk sizes below were calibrated through iterative testing to balance attention quality against context sufficiency.

### Detail Tasks (800--1,200 words)

These are tasks where **every token matters** and the model needs to examine content at the finest granularity.

| Agent | Target Size | Rationale |
|---|---|---|
| **math-logic** | 800--1,200 words | Equation verification requires checking every symbol, subscript, and algebraic step. A focused chunk ensures the model examines each derivation line-by-line rather than glossing over complex expressions. |
| **notation** | 800--1,200 words | Symbol consistency checking requires building a mental inventory of every variable and tracing each occurrence. Smaller chunks produce more complete inventories per pass. |

At this chunk size, a typical Sonnet-class model allocates strong attention to every token. The model can "hold" the entire chunk in active working memory while performing its analysis.

### Flow Tasks (1,500--2,500 words)

These are tasks where **logical connections between paragraphs** matter and the model needs enough context to evaluate transitions, narrative flow, and argument structure.

| Agent | Target Size | Rationale |
|---|---|---|
| **exposition** | 1,500--2,500 words | Evaluating argument flow requires seeing how paragraphs connect. A chunk that is too small (500 words) makes it impossible to assess transitions; a chunk that is too large (4,000 words) dilutes attention to the point where awkward transitions are missed. |
| **language** | 1,500--2,000 words | Language pattern detection (e.g., systematic article omission by L2 speakers) requires enough text to identify *patterns* rather than isolated instances. A single paragraph might not reveal the pattern; 1,500--2,000 words typically contains enough examples. |
| **econometrics** | 1,200--1,800 words | Methodology assessment requires seeing the full specification (model description + estimation approach + assumption discussion) in one view. Methodology sections in economics papers typically span 1,000--2,000 words. |
| **empirical** | 1,000--1,500 words | Cross-checking tables against text requires the table + the surrounding discussion to be in the same chunk. Tables with their discussion typically span 800--1,500 words. |

### Cross-Section Pairs (2,000--3,000 words total)

The cross-section agent receives **pairs of sections** to compare:

| Pair Type | Total Size | Rationale |
|---|---|---|
| Introduction + Results | 2,000--3,000 | Do the results support the claims made in the introduction? |
| Methods + Results | 2,000--3,000 | Do the results match the methodology described? |
| Abstract + Conclusion | 2,000--3,000 | Is the abstract consistent with the conclusion? |
| Literature + Own Approach | 2,000--3,000 | Does the paper criticise approaches it then uses itself? |

Each pair needs both sections to be present in the chunk for meaningful comparison. The 2,000--3,000 word total accommodates two moderate-length sections.

### Full-Section Tasks

| Agent | Target Size | Rationale |
|---|---|---|
| **literature** | Full literature review section | The literature review must be evaluated as a coherent whole to assess coverage, positioning, and gap identification. Splitting it would prevent the agent from detecting which streams of literature are missing entirely. |
| **references** | 15--20 references per batch | Reference verification is I/O-bound (API calls), not attention-bound. Batching references in groups of 15--20 balances API throughput against memory for tracking verification status. |

---

## Adaptive Sizing

Not all papers are structured the same way. The chunking system adapts to the actual content:

### Content Density Detection

Sections vary in density. A section with 5 equations in 500 words is denser than a section with pure prose in 2,000 words. The paper-parser agent classifies each chunk:

- `has_equations` -- contains LaTeX math expressions
- `has_tables` -- contains markdown table syntax
- `has_figures` -- contains figure references or image markup
- `is_references` -- is the bibliography section
- `is_abstract` -- is the abstract

Chunks tagged with `has_equations` are assigned to the math-logic agent at the smaller chunk size (800--1,200 words) to ensure focused analysis of each equation.

### Section Boundary Respect

The primary split is always at heading boundaries (`##`, `###`). This ensures that chunks correspond to logical units of the paper. The secondary split (at paragraph boundaries) only triggers when a section exceeds the target chunk size for a given dimension.

This means that a short section (e.g., a 400-word "Data Description") is kept intact even if it is below the target size. Artificially padding it with content from another section would create incoherent chunks.

### Minimum Chunk Size

Chunks smaller than 200 words are merged with their nearest neighbour rather than being analysed independently. Very short chunks (e.g., a one-paragraph acknowledgments section) do not contain enough content for meaningful analysis.

---

## Overlap Strategy

Adjacent chunks share 150--200 words of overlap at their boundaries. This overlap serves two purposes:

1. **Context continuity** -- When a finding references text near a chunk boundary, the overlap ensures the agent has enough surrounding context to accurately assess the issue. Without overlap, an equation at the end of one chunk might be analysed without seeing the assumptions stated at the beginning of the next chunk.

2. **Boundary robustness** -- Issues that span a chunk boundary (e.g., a paragraph that starts in one chunk and ends in the next) are captured by both chunks, reducing the chance of missing boundary-spanning problems.

The overlap size of 150--200 words was chosen as a balance: large enough to provide meaningful context, small enough to avoid significant redundancy in agent processing time.

---

## PhD Dissertations

PhD dissertations (100--200 pages) require a modified chunking strategy:

### Chapter-by-Chapter Analysis

Each chapter is treated as a semi-independent unit:

1. The paper-parser first splits the dissertation into chapters
2. Each chapter is then chunked independently using the dimension-specific sizes above
3. The cross-section agent receives chapter pairs in addition to within-chapter section pairs

### Cross-Chapter Analysis

In addition to the standard cross-section pairs, the following chapter-level pairs are created:

| Pair | Purpose |
|---|---|
| Introduction chapter + each results chapter | Verify that the dissertation delivers on its stated promises |
| Each methodology chapter + its results chapter | Verify methodology-results consistency per study |
| First chapter + last chapter | Overall coherence of the dissertation arc |

### Scaling Considerations

A 150-page dissertation with 50,000 words produces approximately 50--80 chunks, compared to 15--25 for a journal article. This means:

- Phase 3 (parallel analysis) takes proportionally longer
- The confidence-checker and precision-validator have more findings to process
- Total review time is typically 60--90 minutes vs. 15--30 minutes for an article

The system reports estimated completion time at the start of the review based on the word count and document type.

---

## Figure Integration

When the PDF conversion extracts figure images (via `--extract-figures`):

1. **Empirical agent** receives figure image paths alongside text chunks containing figure references
2. The orchestrator instructs the agent to use the Read tool on each figure image to verify text claims about trends, values, or patterns visible in the figure
3. Chunks tagged with `has_figures: true` receive special attention: the empirical agent must cross-check any text claims about visual evidence against the extracted images
4. If figure extraction fails or produces no images, the empirical agent is instructed to flag unverifiable text-figure claims as a limitation

---

## Multi-Workflow Architecture

The review system supports a triple-workflow architecture that runs three parallel analysis strategies on the same paper, then synthesizes their findings. This maximises coverage by exploiting complementary strengths of each input format.

### Architecture Overview

```
                         ┌── Workflow A: Enhanced MD → Chunks → 7 agents ──┐
Original PDF ──────────► ├── Workflow B: Full PDF (no chunking) → 7 agents ─┼──► Synthesis → Final Review
                         └── Workflow C: PDF page-chunks → 7 agents ────────┘
                         └── Shared: literature + references agents ────────┘
```

### Workflow A — Enhanced Markdown Chunks

This is the existing workflow, enhanced with page boundary markers (`<!-- page N -->`) for post-synthesis location mapping.

- **Input**: PDF → `pdf_to_markdown.py --enhanced` → heading-based chunks
- **Chunk sizes**: As described in the dimension-specific sections above
- **Strengths**: Best text fidelity for prose analysis, clean markdown tables, paragraph-level granularity
- **Weaknesses**: Conversion can garble complex tables, lose equation formatting, mishandle multi-column layouts

### Workflow B — Full PDF, No Chunking

Agents read the entire original PDF directly via the `Read` tool's `pages` parameter, with no markdown conversion step.

- **Input**: Original PDF, read in overlapping segments
- **Segment strategy**:
  - Papers ≤ 20 pages: single `Read(pages="1-20")`
  - Papers 21--40 pages: two overlapping reads, e.g., `Read(pages="1-20")` then `Read(pages="15-40")` (5-page overlap)
  - Papers > 40 pages: three or more overlapping reads with 5-page overlaps
- **Attention management**: Agents receive explicit instructions to "work through the paper section by section systematically" to counteract attention dilution on large reads
- **Strengths**: Zero conversion loss — agents see exactly what humans see (tables, equations, figures, formatting)
- **Weaknesses**: Attention dilution on long documents; no chunk-level focus; figures may not be as easily compared with text

### Workflow C — PDF Page-Range Chunks

Agents read PDF page ranges corresponding to logical sections, as determined by `pdf_section_map.py`.

- **Input**: Original PDF + `pdf_section_map.json` (heading → page range mappings)
- **Chunk sizes**: Determined by section boundaries in the PDF, grouped to approximate the dimension-specific targets
- **Strengths**: Combines PDF fidelity with focused analysis; agents see original tables and figures in context
- **Weaknesses**: Section detection relies on font-size heuristics, which can fail on non-standard layouts; page boundaries may split sentences

### Prompt Differences by Workflow

| Aspect | Workflow A | Workflow B | Workflow C |
|--------|-----------|-----------|-----------|
| Input format | MD file + line ranges | PDF + page segments | PDF + page ranges |
| Location refs | Line numbers + section | Page numbers + section | Page numbers + section |
| Evidence quotes | Markdown text | PDF-rendered text | PDF-rendered text |
| Table/figure handling | MD tables + extracted images | Direct PDF rendering | Direct PDF rendering |
| Attention strategy | Focused chunks | Full-doc systematic scan | Focused page-range chunks |

### Cross-Workflow Synthesis

After all three workflows complete, a synthesis agent (Opus) merges the three finding sets:

1. **Normalise locations** — Map Workflow A line numbers to page numbers using `<!-- page N -->` markers
2. **Group findings** — Cluster by semantic similarity (same page ±1, same agent type, evidence text overlap ≥ 0.7)
3. **Classify groups**:
   - **Shared** (found by 2-3 workflows): Take highest-confidence version; confidence boost +5
   - **Unique** (found by 1 workflow only): Re-verify against original PDF; include if confirmed, else demote to appendix
   - **Contradicted** (conflicting assessments): Resolve by re-reading original PDF
4. **Deduplicate** — Produce single unified findings list
5. **Document provenance** — Record which workflow(s) caught each finding in `synthesis/dedup_map.json`

### Trade-offs

| Factor | Single Workflow | Triple Workflow |
|--------|----------------|-----------------|
| Wall-clock time | ~30 min (article) | ~60 min (article) |
| Agent count | 7-9 | 21-23 |
| Finding coverage | Baseline | +15-25% estimated |
| False positives | Baseline | Lower (cross-validation) |
| Compute cost | 1× | ~3× |

The triple-workflow mode is recommended for final-submission reviews where maximum coverage justifies the additional compute. For draft-stage reviews, the single-workflow (Workflow A) mode remains the default.
