---
name: review
description: Produces a top-journal-quality referee report for a scientific paper (PDF). Handles English and Hungarian papers, articles and PhD dissertations.
user-invocable: true
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, WebSearch, WebFetch, TodoWrite, mcp__Claude_in_Chrome__navigate, mcp__Claude_in_Chrome__read_page, mcp__Claude_in_Chrome__find, mcp__Claude_in_Chrome__computer, mcp__Claude_in_Chrome__get_page_text, mcp__Claude_in_Chrome__tabs_context_mcp, mcp__Claude_in_Chrome__tabs_create_mcp
---

# Scientific Paper Review Orchestrator

You are conducting a rigorous, multi-pass scientific paper review that produces a referee report matching the quality expectations of top-ranked academic journals (AER, QJE, Econometrica, JFE, REStat, JOLE, JDE).

**Input:** `$ARGUMENTS` — path to a PDF file of a scientific paper or PhD dissertation.

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

1. Read the PDF path from `$ARGUMENTS`. If no path provided, ask the user.
2. Create a review directory:
   ```
   reviews/[paper_name]_[YYYY-MM-DD]/
   ├── input/
   ├── verification/
   ├── chunks/
   ├── agent_outputs/
   └── output/
   ```
3. Copy/symlink the PDF into `input/original.pdf`.

### Phase 1 — PDF Conversion & Verification

1. Run: `.venv/bin/python scripts/pdf_to_markdown.py "$PDF_PATH" --output-dir reviews/[name]/input/`
2. Run: `.venv/bin/python scripts/verify_conversion.py "$PDF_PATH" reviews/[name]/input/*_converted.md`
3. Read the verification report.
   - **PASS/WARN**: Proceed. Show any warnings to the user.
   - **FAIL**: STOP. Show failures. Ask user to inspect the markdown or provide an alternative.
4. Read the converted markdown to determine:
   - **Language**: English or Hungarian (check for Hungarian words, diacritics, structure)
   - **Document type**: Article (~5-40 pages) or PhD dissertation (~100-200 pages)
   - **Word count**: from the conversion stats
5. Report: "Paper: [title], Language: [lang], Type: [type], [N] words, [N] pages"
6. Estimate completion time based on the time table in the plan.

### Phase 2 — Chunking

Read the converted markdown and identify chunk boundaries:

1. **Primary split**: by markdown headings (`##`, `###`)
2. **Secondary split**: if any section exceeds the dimension-specific target size, split at paragraph breaks
3. Create `chunks/chunk_map.json` with:
   ```json
   [{"id": "c1", "heading": "1. Introduction", "start_line": 1, "end_line": 45, "words": 1200}]
   ```
4. Note which chunks contain: equations, tables, figures, references

### Phase 3 — Parallel Analysis (launch ALL agents simultaneously)

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
3. **exposition** — Give it ALL chunks in groups of 3-4 (chunk size: 1500-2500 words)
4. **empirical** — Give it chunks with tables/figures + surrounding text (chunk size: 1000-1500 words)
5. **cross-section** — Give it PAIRS of related chunks: intro↔results, methods↔results, abstract↔conclusion (chunk size: 2000-3000 words per pair)
6. **econometrics** — Give it methodology chunks FIRST, then results chunks. Instruct design-before-results evaluation. (chunk size: 1200-1800 words)
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
2. Use WebSearch to find potentially missing key references in the field
3. If Chrome browser is available (Claude in Chrome MCP), search Google Scholar:
   - Open Google Scholar in a tab
   - Search for 3-5 key term combinations
   - Wait 3-8 seconds (random) between searches
   - Extract top results and compare with paper's bibliography
4. Save findings to `agent_outputs/literature.md`

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
6. **Literature and References**: Assessment + verification summary
7. **Language and Presentation**: Constructive suggestions
8. **Suggestions for Improvement**: Optional enhancements
9. **Appendices**: Detailed findings table, low-confidence findings, methodology notes

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
