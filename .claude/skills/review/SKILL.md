---
name: review
description: Produces a top-journal-quality referee report for a scientific paper (PDF). Handles English and Hungarian papers, articles and PhD dissertations.
user-invocable: true
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, WebSearch, WebFetch, TodoWrite, mcp__Claude_in_Chrome__navigate, mcp__Claude_in_Chrome__read_page, mcp__Claude_in_Chrome__find, mcp__Claude_in_Chrome__computer, mcp__Claude_in_Chrome__get_page_text, mcp__Claude_in_Chrome__tabs_context_mcp, mcp__Claude_in_Chrome__tabs_create_mcp
---

# Scientific Paper Review Orchestrator

You are conducting a rigorous, multi-pass scientific paper review that produces a referee report matching the quality expectations of top-ranked academic journals (AER, QJE, Econometrica, JFE, REStat, JOLE, JDE).

**Input:** `$ARGUMENTS` — optional path to a PDF file, optionally followed by `--triple` to enable triple-workflow mode. If omitted, the user should upload/attach a PDF in the conversation before invoking `/review`.

**Mode selection:**
- `/review paper.pdf` — single-workflow mode (default, faster)
- `/review paper.pdf --triple` — triple-workflow mode (3× compute, +15-25% finding coverage)
- If `$ARGUMENTS` contains `--triple`, enable triple-workflow mode and strip the flag from the PDF path.

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
3. Create a review directory. Use the layout matching the chosen mode:

   **Single-workflow mode (default):**
   ```
   reviews/[paper_name]_[YYYY-MM-DD]/
   ├── input/
   ├── verification/
   ├── chunks/
   ├── agent_outputs/
   └── output/
   ```

   **Triple-workflow mode:**
   ```
   reviews/[paper_name]_[YYYY-MM-DD]/
   ├── input/
   ├── verification/
   ├── chunks/
   ├── pdf_chunks/
   ├── agent_outputs/
   │   ├── workflow_a/
   │   ├── workflow_b/
   │   ├── workflow_c/
   │   ├── shared/
   │   └── synthesis/
   └── output/
   ```
4. Copy/symlink the PDF into `input/original.pdf`.

### Phase 1 — PDF Conversion & Verification

**Standard mode (single workflow):**
1. Run: `.venv/bin/python scripts/pdf_to_markdown.py "$PDF_PATH" --output-dir reviews/[name]/input/ --extract-figures`

**Triple-workflow mode:**
1. Run: `.venv/bin/python scripts/pdf_to_markdown.py "$PDF_PATH" --output-dir reviews/[name]/input/ --extract-figures --enhanced`
   - This inserts `<!-- page N -->` markers for PDF-MD location mapping
   - Improves table extraction using pymupdf's structured table finder
   - Detects and logs multi-column pages
2. Run: `.venv/bin/python scripts/pdf_section_map.py "$PDF_PATH" --output reviews/[name]/pdf_chunks/pdf_section_map.json`
   - Maps section headings to page ranges for Workflow C agents
3. Calculate Workflow B page segments:
   - Papers ≤ 20 pages: single segment `1-[total]`
   - Papers 21-40 pages: two overlapping segments with 5-page overlap
   - Papers > 40 pages: three+ overlapping segments with 5-page overlap
   - Record segments in manifest for Phase 3

**Both modes (continue):**
4. Run: `.venv/bin/python scripts/verify_conversion.py "$PDF_PATH" reviews/[name]/input/*_converted.md`
5. Read the verification report.
   - **PASS/WARN**: Proceed. Show any warnings to the user.
   - **FAIL**: STOP. Show failures. Ask user to inspect the markdown or provide an alternative.
6. Catalog any extracted figure images in `input/figures/`. If figures were extracted, note their paths for use in Phase 3 (empirical agent).
7. Read the converted markdown to determine:
   - **Language**: English or Hungarian (check for Hungarian words, diacritics, structure)
   - **Document type**: Article (~5-40 pages) or PhD dissertation (~100-200 pages)
   - **Word count**: from the conversion stats
8. Report: "Paper: [title], Language: [lang], Type: [type], [N] words, [N] pages, [N] figures extracted"
9. Estimate completion time: ~30 min for single-workflow articles, ~60 min for triple-workflow articles, ~60-90 min for dissertations.

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

#### Common Agent Instructions (all workflows)

For each agent, provide:
- Reminder to use **assertion-style finding titles** (see `.claude/rules/review-standards.md`)
- Reference to `.claude/rules/statistical-pitfalls.md` for awareness of common pitfalls
- The abstract + introduction text (for context)

**CRITICAL: Design-Before-Results Order for Econometrics Agent**
The econometrics agent MUST evaluate the research DESIGN (methodology/identification strategy) BEFORE reading results. Tell it explicitly: "Assess the methodology section first. Form your design assessment. Then read results." This prevents anchoring bias.

#### Agent Dimension Prompts

These dimension-specific instructions apply to ALL workflows (A, B, and C). The only difference across workflows is the input format (see workflow-specific sections below).

1. **math-logic** — Analyze equations/proofs (Workflow A chunk size: 800-1200 words)
2. **notation** — Analyze ALL content in groups (Workflow A chunk size: 800-1200 words)
3. **exposition** — Analyze ALL content in groups (Workflow A chunk size: 1500-2500 words). Include these additional checks in the prompt:
   - **Terminological precision**: When a key term (e.g., "gender-balanced," "feminisation," "equality") is used in multiple places, verify it carries a consistent meaning. Flag cases where a term is ambiguous or shifts meaning across sections.
   - **Descriptive-to-causal language gap**: When the methodology is purely descriptive (correlations, time-series plots), verify that the interpretation and discussion do not slide into causal language ("leads to," "causes," "drives," "results in") without appropriate qualification. This is especially important in Discussion and Conclusions sections.
   - **List parallelism and category errors**: In complex enumerations, verify that listed items are grammatically parallel and belong to the same semantic category (e.g., don't mix professions with health systems, or causes with effects).
   - **Dangling references and missing antecedents**: Flag definite references ("the two countries," "these mechanisms," "this gap") that lack clear antecedents in the immediately preceding text. Also check for scope mismatches (e.g., a paragraph framed in general terms suddenly using "the two countries" without specifying which pair).
   - **Redundant and garbled phrasing**: Flag phrases that repeat a word or concept within the same noun phrase (e.g., "the division of the GVC division of labor"), creating confusion about the intended meaning.
   - **Illogical transition words**: Flag connectors that contradict the logical relationship between sentences (e.g., "However" used in a non-contrastive context, "On the one hand" without a corresponding "on the other hand").
   - **Chronological confusion in temporal narratives**: When text uses a staged/periodic framework, verify that the narrative consistently signals which stage is being discussed and does not slip between stages without transition (e.g., discussing "since 2020" then suddenly referencing "in the early days" within the same paragraph).
4. **empirical** — Analyze content with tables/figures (Workflow A chunk size: 1000-1500 words). If figure images were extracted in Phase 1, pass their file paths and instruct the agent to use the Read tool on each image to verify text claims. Include these additional checks:
   - **Figure verification**: Compare text claims about figures with the visual evidence. If no figure images are available, flag text-figure claims that cannot be verified from tables alone.
   - **Universal qualifier audit**: When text uses "uniformly," "always," "in every country," "without exception," or similar universal quantifiers, verify against ALL data points in the relevant table. Check for missing values (N/A), non-significant estimates, and exceptions.
   - **Coverage matrix awareness**: When a table contains variable sample sizes across cells, note whether the text acknowledges this and whether conclusions drawn from sparse cells (N<10) are appropriately qualified.
   - **Figure interpretation validity**: When the text describes what a figure "shows" (e.g., "the network has shifted from US-centric to multipolar"), verify that the figure type actually supports that interpretation. A VOSviewer keyword co-occurrence map shows bibliometric term relationships, NOT geopolitical networks of rule diffusion. A citation network shows intellectual lineage, NOT institutional influence. Flag mismatches between the visualisation method and the analytical claims made about it.
   - **Temporal consistency in cited data**: When statistics cite a report from year Y but describe data for year Y-1 as "expected" or "projected," flag the potential temporal mismatch — the figure may be a realised value rather than a projection, or vice versa.
5. **cross-section** — Analyze PAIRS of related sections: intro↔results, methods↔results, abstract↔conclusion (Workflow A chunk size: 2000-3000 words per pair). Include these additional checks:
   - **Abstract paradox clarity**: If the paper coins or introduces a key concept (e.g., a "paradox," "puzzle," or "stylised fact"), verify that the abstract's framing is precise and cannot be misread as contradicting the paper's own findings.
   - **Table classification vs text narrative consistency**: When a table classifies items into categories (e.g., studies assigned to historical stages, methods assigned to types), verify that (a) the organising principle is explicitly stated (is classification by topic, by time period studied, or by publication date?), and (b) items are not placed contradictorily across the text narrative and the table (e.g., a study discussed in the "early phase" paragraph but classified under "maturity" in the table).
6. **econometrics** — Analyze methodology FIRST, then results. Instruct design-before-results evaluation. (Workflow A chunk size: 1200-1800 words). Include these additional checks:
   - **Data harmonisation assessment**: Before evaluating the statistical methodology, assess data quality: (a) Are variables from different sources defined consistently? Check for headcount vs FTE, practising vs professionally active vs licensed. (b) Does the paper explain how indicators from different sources were harmonised? (c) Are observation windows comparable across countries/units and indicators? (d) Are series breaks or reclassifications acknowledged? This is especially important for cross-country studies combining multiple international databases.
   - **Construct definition**: Does the paper operationally define its central construct before using it in research questions, inclusion criteria, or empirical operationalisation? A systematic review of "digital trade rules" must define what counts as a rule; an empirical study of "fintech adoption" must define what counts as fintech. Flag missing definitions as Major.
   - **Systematic review methodology** (if paper is a systematic review): (a) Is the search string broad enough to capture all stated research questions, or do mandatory AND terms mechanically exclude relevant literature? (b) Are search field specifications (title/abstract vs full text vs "anywhere") consistent across databases? (c) Is there a documented data extraction form and coding rulebook? (d) Is a quality appraisal instrument applied to included studies? (e) Is the method taxonomy correct — does it properly distinguish model specifications (gravity, structural) from estimation techniques (PPML, OLS, MLE) from identification designs (DID, RDD, IV)?
   - **Sample composition artifacts**: When the paper reports geographic, institutional, or author-affiliation distributions, assess whether these are genuine signals or mechanical artifacts of the search strategy (e.g., Google Scholar "anywhere" disproportionately retrieving certain regions' working papers).
7. **language** — Analyze ALL content in groups (Workflow A chunk size: 1500-2000 words). Include these additional checks:
   - **Chinese academic calque detection** (for papers by Chinese L1 authors): Be alert to common translation artifacts from Chinese academic writing that produce nonstandard or semantically inverted English: "data-free flow" (intended: free flow of data / cross-border data flows), "interactive items" (intended: interaction terms), "regular income" (intended: income distribution / gains), "regulatory role" (intended: moderating role/effect), "depth rules" (intended: deeper rules), "partial distributions" (intended: skewed distributions), "development vein" (intended: development trajectory). Flag these with the standard English term.
   - **Nonstandard terminology that inverts meaning**: Pay special attention to compound phrases where word order or missing hyphens invert the intended meaning (e.g., "data-free flow clauses" can be read as "flow without data" rather than "clauses about free data flow").
   - **Ambiguous citation placement**: When a citation appears between two clauses, flag cases where it is unclear whether the citation supports the methodological claim or provides an additional example (e.g., "(Kim, 2024)" placed between a method description and an application description).

#### Single-Workflow Mode (default)

Launch 7 agents in parallel using **Workflow A** only:
- Provide the path to the converted markdown file, chunk_map.json, and specific line ranges
- Instructions to save findings to `agent_outputs/[agent_name].md`

Report: "Phase 3: All 7 analysis agents launched. Waiting for results..."
As agents complete, report: "Phase 3: [N]/7 dimensions complete."

#### Triple-Workflow Mode

Launch 3×7 = 21 agents in parallel across three workflows. All three workflows use the same dimension prompts above; they differ only in input format and location references.

**Workflow A agents (enhanced markdown chunks):**
- Input: Converted markdown file + chunk_map.json line ranges
- Location references: Line numbers + section names
- Evidence quotes: Markdown text
- Save to `agent_outputs/workflow_a/[agent_name].md`

**Workflow B agents (full PDF, no chunking):**
- Input: Original PDF via `Read(file_path, pages="1-15")` then `Read(file_path, pages="10-26")` etc. (with 5-page overlap for papers > 20 pages; single read for papers ≤ 20 pages)
- Explicit attention instruction: "Work through the paper section by section systematically. For each section, note the section heading and page number before analyzing content."
- Location references: Page numbers + section names
- Evidence quotes: PDF-rendered text
- Save to `agent_outputs/workflow_b/[agent_name].md`

**Workflow C agents (PDF page-range chunks):**
- Input: Original PDF + page ranges from `pdf_chunks/pdf_section_map.json`
- Read dimension assignments from the section map: e.g., `Read(file_path, pages="1-7")` for sections s1-s3
- Location references: Page numbers + section names
- Evidence quotes: PDF-rendered text
- Save to `agent_outputs/workflow_c/[agent_name].md`

Report: "Phase 3: All 21 analysis agents launched (7 per workflow). Waiting for results..."
As agents complete, report: "Phase 3: [N]/21 dimensions complete (A: [N]/7, B: [N]/7, C: [N]/7)."

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
5. Save findings to `agent_outputs/literature.md` (single-workflow) or `agent_outputs/shared/literature.md` (triple-workflow)

Report: "Phase 4: Literature search complete. [N] potentially missing references identified."

### Phase 5 — Reference Verification

1. Run: `.venv/bin/python scripts/verify_references.py reviews/[name]/input/*_references.json --email review@refine-ink.local`
2. Read the verification report
3. For any "unverifiable" references: attempt web search as fallback
4. Launch the **references** agent with the verification results to interpret and flag suspicious entries
5. Save results to `verification/reference_report.json` and `agent_outputs/references.md` (single-workflow) or `agent_outputs/shared/references.md` (triple-workflow)

Report: "Phase 5: References verified. [N] verified, [N] unverifiable, [N] suspicious."

### Phase 6 — Cross-Workflow Synthesis (triple-workflow mode only)

**Skip this phase in single-workflow mode.**

Perform cross-workflow synthesis (inline, using Opus model for quality) to merge findings from all three workflows:

1. **Load** all findings from `workflow_a/`, `workflow_b/`, `workflow_c/`, and `shared/`
2. **Normalise locations** — Map Workflow A line numbers to page numbers using `<!-- page N -->` markers in the enhanced markdown
3. **Group** findings by semantic similarity:
   - Same page ±1 page
   - Same agent type (dimension)
   - Evidence text overlap ≥ 0.7 (fuzzy match)
4. **Classify** each group:
   - **Shared** (found by 2-3 workflows): Take the highest-confidence version; boost confidence by +5 points (capped at 100)
   - **Unique** (found by 1 workflow only): Re-verify against original PDF; include if confirmed, else demote to low-confidence appendix
   - **Contradicted** (conflicting assessments across workflows): Resolve by re-reading original PDF; document the resolution reasoning
5. **Deduplicate** — Produce a single unified findings list
6. **Document provenance** — Write `agent_outputs/synthesis/dedup_map.json` recording:
   ```json
   {
     "finding_id": "F01",
     "sources": ["workflow_a/econometrics", "workflow_c/econometrics"],
     "classification": "shared",
     "confidence_boost": true,
     "original_confidences": [85, 90],
     "final_confidence": 95
   }
   ```

Save merged findings to `agent_outputs/synthesis/merged_findings.md`

Report: "Phase 6: Cross-workflow synthesis complete. [N] raw findings → [N] merged. [N] shared, [N] unique validated, [N] contradictions resolved."

### Phase 7 — Confidence Iteration

1. Collect ALL findings from Phases 3-6 (in single-workflow mode: Phases 3-5; in triple-workflow mode: use the merged findings from Phase 6)
2. Filter findings with confidence < 80%
3. Launch the **confidence-checker** agent with these low-confidence findings + the original PDF (Read tool)
4. Apply the results: confirm, revise, or withdraw findings
5. Save to `agent_outputs/confidence_check.md`

Report: "Phase 7: [N] findings re-analyzed. [N] confirmed, [N] revised, [N] withdrawn."

### Phase 8 — Synthesis & Writing

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

### Phase 9 — Final Precision Validation

Launch the **precision-validator** agent:

**Tier A (internal findings, 95% threshold):**
- Re-verify every finding against the original PDF (use Read tool with pages parameter)
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

Report: "Phase 9: Precision validation complete. [N]% average precision. [N] findings revised, [N] moved to low-confidence appendix."

### Phase 10 — Output Generation

1. Write final review to `output/review_EN.md`
2. Run: `.venv/bin/python scripts/md_to_html.py output/review_EN.md`
3. If Hungarian: write `output/review_HU.md` and convert to HTML
4. Generate `manifest.json` with full audit trail:
   - Timestamps, duration, paper metadata
   - Conversion verification results
   - Chunking details
   - Per-agent statistics (in triple-workflow mode: per-workflow agent stats)
   - Reference verification summary
   - Confidence iteration results
   - Cross-workflow synthesis results (triple-workflow mode)
   - Precision validation results
   - Final findings counts and recommendation

**Extended manifest for triple-workflow mode:**
```json
{
  "phase_3_analysis": {
    "workflow_a": {"method": "markdown_chunks", "findings": 32},
    "workflow_b": {"method": "full_pdf", "segments": ["1-15","10-26"], "findings": 28},
    "workflow_c": {"method": "pdf_section_chunks", "findings": 30}
  },
  "phase_6_synthesis": {
    "raw_findings_total": 90,
    "shared_across_3": 12, "shared_across_2": 18,
    "unique_validated": 8, "unique_unvalidated": 5,
    "contradicted_resolved": 3,
    "final_merged_count": 41
  }
}
```

Report final summary:
```
Review complete.
Paper: [title]
Mode: [single-workflow / triple-workflow]
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
