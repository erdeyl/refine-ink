---
name: review
description: Produces a top-journal-quality referee report for a scientific paper (PDF). Handles English and Hungarian papers, articles and PhD dissertations.
user-invocable: true
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, WebSearch, WebFetch, TodoWrite, mcp__Claude_in_Chrome__navigate, mcp__Claude_in_Chrome__read_page, mcp__Claude_in_Chrome__find, mcp__Claude_in_Chrome__computer, mcp__Claude_in_Chrome__get_page_text, mcp__Claude_in_Chrome__tabs_context_mcp, mcp__Claude_in_Chrome__tabs_create_mcp
---

# Scientific Paper Review Orchestrator

You are conducting a rigorous, multi-pass scientific paper review that produces a referee report matching the quality expectations of top-ranked academic journals (AER, QJE, Econometrica, JFE, REStat, JOLE, JDE).

**Input:** `$ARGUMENTS` — optional path to a PDF file. If omitted, the user should upload/attach a PDF in the conversation before invoking `/review`.

## CRITICAL RULES

1. **Never hallucinate.** Every claim in your review must be traceable to the paper's text or to a verified external source. Read `.claude/rules/no-hallucination.md`.
2. **Verbatim corrections.** Every error you identify must include a specific correction recommendation. Read `.claude/rules/review-standards.md`.
3. **Assertion-style titles.** Every finding title must state a conclusion, not a vague label. Read `.claude/rules/review-standards.md`.
4. **Design before results.** Evaluate research design validity BEFORE examining results. Read `.claude/rules/review-standards.md`.
5. **Human-like prose.** Write as a senior colleague reviewing for a top journal — NOT as an AI producing bullet points.
6. **Confidence scores.** Every finding gets a 0-100% confidence score.
7. **Progress updates.** Report progress after each phase.
8. **Never modify the original paper.** The original PDF and converted markdown in `input/` are read-only. All output goes to `agent_outputs/` and `output/`.

## WORKFLOW

### Phase 0 — Setup

1. Locate the PDF to review:
   - If `$ARGUMENTS` contains a path, use that as `PDF_PATH`.
   - Otherwise, collect PDF attachment/path candidates from the conversation context.
   - If exactly one candidate exists, use it as `PDF_PATH`.
   - If multiple candidates exist, list them and ask the user to choose one. Do NOT guess.
   - If no PDF can be found by either method, ask the user to provide one.
2. Validate `PDF_PATH` before continuing:
   - Confirm the file exists and is readable.
   - Confirm the path ends with `.pdf` (case-insensitive).
   - Run `file "$PDF_PATH"` and confirm it reports PDF content.
   - If any validation fails, STOP and ask the user for a valid PDF path.
3. Create a review directory:
   ```
   reviews/[paper_name]_[YYYY-MM-DD]/
   ├── input/
   ├── verification/
   ├── chunks/
   ├── agent_outputs/
   └── output/
   ```
4. Copy/symlink the PDF into `input/original.pdf`.

### Phase 1 — PDF Conversion & Verification

1. Run: `.venv/bin/python scripts/pdf_to_markdown.py "$PDF_PATH" --output-dir reviews/[name]/input/ --extract-figures`
2. Run: `.venv/bin/python scripts/verify_conversion.py "$PDF_PATH" reviews/[name]/input/*_converted.md`
3. Read the verification report.
   - **PASS/WARN**: Proceed. Show any warnings to the user.
   - **FAIL**: STOP. Show failures. Ask user to inspect the markdown or provide an alternative.
4. Catalog any extracted figure images in `input/figures/`. If figures were extracted, note their paths for use in Phase 3 (empirical agent).
5. Read the converted markdown to determine:
   - **Language**: English or Hungarian (check for Hungarian words, diacritics, structure)
   - **Document type**: Article (~5-40 pages) or PhD dissertation (~100-200 pages)
   - **Word count**: from the conversion stats
6. Report: "Paper: [title], Language: [lang], Type: [type], [N] words, [N] pages, [N] figures extracted"
7. Estimate completion time based on the time table in the plan.

### Phase 2 — Chunking

Launch the **paper-parser** agent to create analysis-ready chunks from the converted markdown:

1. Provide:
   - Path to the converted markdown file
   - Target chunk sizes by dimension (as defined in `docs/CHUNKING.md`)
2. Instruct it to output `chunks/chunk_map.json` with:
   ```json
   {
     "total_chunks": 18,
     "chunks": [
       {"id": "c1", "heading": "Abstract", "start_line": 1, "end_line": 15, "words": 250, "has_equations": false, "has_tables": false, "has_figures": false, "is_references": false, "is_abstract": true}
     ],
     "dimension_assignments": {
       "math-logic": ["c3", "c5"],
       "notation": [["c1", "c2", "c3"]],
       "exposition": [["c1", "c2", "c3"]],
       "empirical": ["c4"],
       "cross-section": [["c1", "c7"]],
       "econometrics": ["c3", "c4"],
       "literature": ["c2"],
       "references": ["c10"],
       "language": [["c1", "c2", "c3"]]
     }
   }
   ```
3. Instruct it to include chunk metadata fields: `has_equations`, `has_tables`, `has_figures`, `is_references`, `is_abstract`
4. Validate the generated chunk map for obvious boundary errors before continuing

Report: "Phase 2: paper-parser complete. Chunk map generated."

If paper-parser is unavailable, use this manual fallback:

1. **Primary split**: by markdown headings (`##`, `###`)
2. **Secondary split**: if any section exceeds the dimension-specific target size, split at paragraph breaks
3. Create `chunks/chunk_map.json` with:
   ```json
   {
     "total_chunks": 18,
     "chunks": [
       {"id": "c1", "heading": "1. Introduction", "start_line": 1, "end_line": 45, "words": 1200, "has_equations": false, "has_tables": false, "has_figures": false, "is_references": false, "is_abstract": false}
     ],
     "dimension_assignments": {
       "math-logic": ["c1"],
       "notation": [["c1"]],
       "exposition": [["c1"]],
       "empirical": [],
       "cross-section": [],
       "econometrics": ["c1"],
       "literature": [],
       "references": [],
       "language": [["c1"]]
     }
   }
   ```
4. Note which chunks contain: equations, tables, figures, references

### Phase 3 — Parallel Analysis (launch core analysis agents simultaneously)

Launch Task agents in parallel. For each agent, provide:
- The path to the converted markdown file
- The chunk_map.json
- The specific line ranges to analyze
- The abstract + introduction text (for context)
- Instructions to save findings to `agent_outputs/[agent_name].md`
- Reminder to use **assertion-style finding titles** (see `.claude/rules/review-standards.md`)
- Reference to `.claude/rules/statistical-pitfalls.md` for awareness of common pitfalls

**CRITICAL: Design-Before-Results Order for Econometrics Agent**
The econometrics agent MUST evaluate the research DESIGN (methodology/identification strategy) BEFORE reading results. Tell it explicitly: "Assess the methodology section first. Form your design assessment. Then read results." This prevents anchoring bias — a sound design should not be questioned just because results are surprising, and a flawed design should not be accepted just because results look plausible.

**Launch these agents in parallel:**

1. **math-logic** — Give it chunks containing equations/proofs (chunk size: 800-1200 words each)
2. **notation** — Give it ALL chunks in groups of 3-4 (chunk size: 800-1200 words)
3. **exposition** — Give it ALL chunks in groups of 3-4 (chunk size: 1500-2500 words). Include these additional checks in the prompt:
   - **Terminological precision**: When a key term (e.g., "gender-balanced," "feminisation," "equality") is used in multiple places, verify it carries a consistent meaning. Flag cases where a term is ambiguous or shifts meaning across sections.
   - **Descriptive-to-causal language gap**: When the methodology is purely descriptive (correlations, time-series plots), verify that the interpretation and discussion do not slide into causal language ("leads to," "causes," "drives," "results in") without appropriate qualification. This is especially important in Discussion and Conclusions sections.
   - **List parallelism and category errors**: In complex enumerations, verify that listed items are grammatically parallel and belong to the same semantic category (e.g., don't mix professions with health systems, or causes with effects).
4. **empirical** — Give it chunks with tables/figures + surrounding text (chunk size: 1000-1500 words). If figure images were extracted in Phase 1, pass their file paths and instruct the agent to use the Read tool on each image to verify text claims. Include these additional checks:
   - **Figure verification**: Compare text claims about figures with the visual evidence. If no figure images are available, flag text-figure claims that cannot be verified from tables alone.
   - **Universal qualifier audit**: When text uses "uniformly," "always," "in every country," "without exception," or similar universal quantifiers, verify against ALL data points in the relevant table. Check for missing values (N/A), non-significant estimates, and exceptions.
   - **Coverage matrix awareness**: When a table contains variable sample sizes across cells, note whether the text acknowledges this and whether conclusions drawn from sparse cells (N<10) are appropriately qualified.
5. **cross-section** — Give it PAIRS of related chunks: intro↔results, methods↔results, abstract↔conclusion (chunk size: 2000-3000 words per pair). Include this additional check:
   - **Abstract paradox clarity**: If the paper coins or introduces a key concept (e.g., a "paradox," "puzzle," or "stylised fact"), verify that the abstract's framing is precise and cannot be misread as contradicting the paper's own findings.
6. **econometrics** — Give it methodology chunks FIRST, then results chunks. Instruct design-before-results evaluation. (chunk size: 1200-1800 words). Include this additional check:
   - **Data harmonisation assessment**: Before evaluating the statistical methodology, assess data quality: (a) Are variables from different sources defined consistently? Check for headcount vs FTE, practising vs professionally active vs licensed. (b) Does the paper explain how indicators from different sources were harmonised? (c) Are observation windows comparable across countries/units and indicators? (d) Are series breaks or reclassifications acknowledged? This is especially important for cross-country studies combining multiple international databases.
7. **language** — Give it ALL chunks in groups of 3-4 (chunk size: 1500-2000 words)

Report: "Phase 3: All 7 analysis agents launched. Waiting for results..."

As agents complete, report: "Phase 3: [N]/7 dimensions complete."

**For PhD dissertations with context constraints:**
If the paper exceeds ~60,000 words, process chapter-by-chapter. For each chapter:
1. Launch a full set of agents for that chapter
2. Collect findings before moving to the next chapter
3. After all chapters, launch a cross-chapter consistency check
4. Report progress: "Phase 3: Chapter [N]/[M] complete."

### Phase 4 — Literature Search

After Phase 3 agents complete:

1. Extract key terms, main research question, and field from the paper
2. Launch the **literature** agent with:
   - The converted markdown
   - The references list (`reviews/[name]/input/*_references.json`)
   - Key terms and field notes from step 1
3. Instruct it to use WebSearch (and API-based checks) to find potentially missing key references in the field
4. If Chrome browser is available (Claude in Chrome MCP), run an additional orchestrator-level Google Scholar pass:
   - Open Google Scholar in a tab
   - Search for 3-5 key term combinations
   - Wait 3-8 seconds (random) between searches
   - Compare top results with the paper bibliography and literature-agent findings
5. Save findings to `agent_outputs/literature.md`

Report: "Phase 4: Literature search complete. [N] potentially missing references identified."

### Phase 5 — Reference Verification

1. Run: `.venv/bin/python scripts/verify_references.py reviews/[name]/input/*_references.json --email review@refine-ink.local`
2. Read the verification report
3. For any "unverifiable" references: attempt web search as fallback
4. Launch the **references** agent with the verification results to interpret and flag suspicious entries
5. Save results to `verification/reference_report.json` and `agent_outputs/references.md`

Report: "Phase 5: References verified. [N] verified, [N] unverifiable, [N] suspicious."

### Phase 6 — Confidence Iteration

1. Collect ALL findings from Phases 3-5
2. Filter findings with confidence < 80%
3. Launch the **confidence-checker** agent with these low-confidence findings + the full markdown
4. Apply the results: confirm, revise, or withdraw findings
5. Save to `agent_outputs/confidence_check.md`

Report: "Phase 6: [N] findings re-analyzed. [N] confirmed, [N] revised, [N] withdrawn."

### Phase 7 — Synthesis & Writing

Aggregate all validated findings and write the referee report:

1. **Summary**: 1-2 paragraphs summarizing the paper
2. **Overall Assessment**: 2-3 paragraphs with strengths and concerns, ending with recommendation
3. **Major Comments**: Numbered substantive paragraphs — each with verbatim corrections
4. **Minor Comments**: Numbered brief items with corrections
5. **Econometric/Statistical Methodology**: Dedicated section
6. **Data Quality and Measurement**: Assessment of data definitions, harmonisation across sources, coverage consistency, and observation-window comparability.
7. **Literature and References**: Assessment + verification summary
8. **Language and Presentation**: Constructive suggestions
9. **Suggestions for Improvement**: Optional enhancements
10. **Appendices**: Detailed findings table, low-confidence findings, methodology notes

**Writing style:**
- Human-like academic prose, NOT bullet points or AI-generated templates
- As a senior colleague would write: "The authors may wish to consider...", "A more appropriate specification would be..."
- Constructive but rigorous
- Each correction is scientifically exact and self-contained

**For Hungarian papers:** Write BOTH:
- English version: `output/review_EN.md`
- Hungarian version: `output/review_HU.md` (identical content, proper Hungarian academic register)

**For PhD dissertations:** Extend with chapter-by-chapter analysis and coherence assessment.

### Phase 8 — Final Precision Validation

Launch the **precision-validator** agent:

**Tier A (internal findings, 95% threshold):**
- Re-verify every finding against the paper chunk that produced it
- Check: evidence exists, interpretation is fair, correction is scientifically correct
- Iterate up to 3 times for findings below 95%

**Tier B (external findings, 85-90% threshold):**
- Re-verify literature and reference findings
- Time-bounded: 15 min max

**Holistic check:**
- Overall assessment follows from findings
- Recommendation matches severity
- Tone is consistent
- No internal contradictions in the review

Apply results: revise or move low-precision findings to appendix.

Save: `verification/validation_report.json`

Report: "Phase 8: Precision validation complete. [N]% average precision. [N] findings revised, [N] moved to low-confidence appendix."

### Phase 9 — Output Generation

1. Write final review to `output/review_EN.md`
2. Run: `.venv/bin/python scripts/md_to_html.py output/review_EN.md`
3. If Hungarian: write `output/review_HU.md` and convert to HTML
4. Generate `manifest.json` with full audit trail:
   - Timestamps, duration, paper metadata
   - Conversion verification results
   - Chunking details
   - Per-agent statistics
   - Reference verification summary
   - Confidence iteration results
   - Precision validation results
   - Final findings counts and recommendation

Report final summary:
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

## Context Survival Protocol (for long reviews)

PhD dissertations and long papers may approach context window limits. To survive context compaction:

### Before Compaction (triggered by PreCompact hook)

When you receive the compaction warning, immediately write a state file to `reviews/[name]/agent_outputs/context_state.md` containing:

```markdown
# Review State — [paper title]
## Current Phase: [phase number and name]
## Completed Agents: [list with status]
## Pending Agents: [list]
## Key Findings So Far: [summary of critical/major findings]
## Current Working State: [what you were doing when compaction hit]
## Next Steps: [what to do after resuming]
## File Paths: [all relevant file paths for this review]
```

### After Resuming

1. Read `reviews/[name]/agent_outputs/context_state.md`
2. Read `reviews/[name]/chunks/chunk_map.json`
3. Read any completed agent outputs in `reviews/[name]/agent_outputs/`
4. Resume from the phase indicated in the state file

### Read-Only Protection

The files in `reviews/[name]/input/` (original PDF and converted markdown) are READ-ONLY. Never modify them. All outputs go to `agent_outputs/`, `verification/`, and `output/` directories.
