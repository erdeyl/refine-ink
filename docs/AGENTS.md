# Agents

This document provides detailed documentation of all agents in the refine-ink system: what each agent checks, how it works, its common findings, limitations, and how agents interact.

---

## Agent Overview

| # | Agent | Model | Tools | Chunk Size | Purpose |
|---|---|---|---|---|---|
| 1 | paper-parser | Haiku | Read, Grep, Glob, Bash, Write | Full document | Parse markdown into analysis-ready chunks |
| 2 | math-logic | Sonnet | Read, Grep, Glob | 800--1,200 words | Verify equations, derivations, proofs |
| 3 | notation | Sonnet | Read, Grep, Glob | 800--1,200 words | Check symbol/variable consistency |
| 4 | exposition | Sonnet | Read, Grep, Glob | 1,500--2,500 words | Evaluate argument flow and clarity |
| 5 | empirical | Sonnet | Read, Grep, Glob | 1,000--1,500 words | Cross-check tables/figures vs. text |
| 6 | cross-section | Sonnet | Read, Grep, Glob | 2,000--3,000 words (paired) | Detect inter-section contradictions |
| 7 | econometrics | Sonnet | Read, Grep, Glob | 1,200--1,800 words | Evaluate statistical methodology |
| 8 | literature | Sonnet | Read, Grep, Glob, WebSearch, Bash | Full section | Assess literature coverage and gaps |
| 9 | references | Sonnet | Read, Grep, Glob, Bash, WebSearch | 15--20 refs/batch | Validate references, detect hallucinations |
| 10 | language | Sonnet | Read, Grep, Glob | 1,500--2,000 words | Evaluate language quality (L2/L3 English, Hungarian) |
| 11 | confidence-checker | Opus | Read, Grep, Glob | Variable (expanded) | Re-verify low-confidence findings |
| 12 | precision-validator | Opus | Read, Grep, Glob | Variable | Final quality gate for all findings |

---

## Agent Details

### 1. paper-parser

**Model**: Haiku
**Phase**: 2 (Chunking)
**Input**: Converted Markdown file + target chunk sizes per dimension
**Output**: `chunks/chunk_map.json`

**What it does:**
- Reads the converted Markdown and identifies section boundaries from headings
- Creates chunks following dimension-specific size targets
- Classifies each chunk by content type (equations, tables, figures, references, abstract)
- Assigns chunks to dimensions based on content classification and size requirements
- Adds 150--200 words of overlap between adjacent chunks

**How it works:**
1. Primary split at heading boundaries (`#`, `##`, `###`)
2. Secondary split at paragraph breaks if a section exceeds the target size
3. Content classification using pattern matching (LaTeX math, markdown tables, image references)
4. Dimension assignment mapping chunks to agents based on content tags

**Common outputs:**
- A `chunk_map.json` with typically 15--25 chunks for a journal article, 50--80 for a dissertation
- Summary statistics: total chunks, chunks per dimension, average chunk size

**Limitations:**
- Depends on the quality of Markdown headings from the PDF conversion
- Papers without clear heading structure produce less optimal chunking

---

### 2. math-logic

**Model**: Sonnet
**Phase**: 3 (Parallel Analysis)
**Input**: Chunks containing equations, proofs, and derivations
**Output**: `agent_outputs/math-logic.md`

**What it checks:**
- Step-by-step verification of every algebraic derivation
- Proof completeness and logical validity
- Sign errors, missing terms, incorrect simplifications
- Division by zero, incorrect differentiation/integration
- Matrix algebra correctness (dimensions, transposition, inverse)
- Statistical formula correctness (estimators, variance, test statistics)
- Logical reasoning: do conclusions follow from evidence?

**How it works:**
1. First pass: understand the mathematical framework and notation
2. Second pass: verify every equation and derivation step-by-step
3. Third pass: check proofs for completeness and logical gaps
4. Fourth pass: cross-reference results (do later results correctly use earlier expressions?)

**Common findings:**
- Sign errors in derivations (positive/negative flips)
- Terms dropped during algebraic manipulation
- Incorrect application of matrix transpose rules
- Degrees of freedom errors in test statistics
- Distributional assumptions used without being stated

**Limitations:**
- Cannot verify numerical computations (e.g., whether a specific coefficient value is correct)
- Very complex proofs may exceed the model's verification capacity; these are flagged as "could not fully verify"
- Does not check statistical correctness of *methodology choice* (that is the econometrics agent's job)

---

### 3. notation

**Model**: Sonnet
**Phase**: 3 (Parallel Analysis)
**Input**: All chunks in groups of 3--4
**Output**: `agent_outputs/notation.md`

**What it checks:**
- Symbol/variable definition before first use
- Cross-section symbol consistency (does $\beta$ mean the same thing throughout?)
- Redefined or overloaded symbols
- Acronym expansion on first use
- Subscript/superscript convention consistency
- Variable name consistency across text, equations, tables, and figures

**How it works:**
1. First pass: build a complete symbol inventory (symbol, definition, first location, all locations)
2. Second pass: trace every symbol through the paper checking for consistency
3. Third pass: check acronym usage
4. Fourth pass: cross-reference variable names in text, equations, tables, and figures

**Common findings:**
- Symbol used before being defined
- Same symbol used with different meanings in different sections (e.g., $i$ indexing individuals in Section 2 and firms in Section 4 without redefinition)
- Subscript conventions changing (e.g., $X_i$ in text, $X^i$ in equations)
- Table column headers not matching equation variable names
- Acronym used in abstract without expansion

**Limitations:**
- Cannot determine whether a notation *choice* is good or bad, only whether it is *consistent*
- Standard mathematical notation ($\mathbb{E}$, $\pi$, etc.) may be flagged as undefined if the agent does not recognise the convention

---

### 4. exposition

**Model**: Sonnet
**Phase**: 3 (Parallel Analysis)
**Input**: All chunks in groups of 3--4
**Output**: `agent_outputs/exposition.md`

**What it checks:**
- Logical flow between sections and within sections
- Ambiguous claims and unclear phrasing
- Abstract-paper alignment (does the abstract match the actual results?)
- Introduction-results alignment
- Unsupported claims (assertions without evidence or citation)
- Figure/table discussion adequacy (every figure/table discussed?)
- Section transitions

**How it works:**
1. First pass: read as a referee would, noting confusion and unclear passages
2. Second pass: check abstract-paper and introduction-results alignment
3. Third pass: check that every figure/table is discussed and descriptions are accurate
4. Fourth pass: evaluate section transitions and overall logical flow

**Common findings:**
- Abstract overstating the contribution relative to actual results
- Introduction claiming causality while results show only correlation
- Paragraphs that could be split for clarity
- Figures included but never discussed in the text
- Vague qualifiers ("somewhat," "fairly") without quantification

**Limitations:**
- Distinguishes between language issues and logic issues; language issues are deferred to the language agent
- For L2/L3 English writers, focuses on clarity of communication rather than stylistic polish
- Subjective assessments (e.g., "this section is boring") are avoided in favour of concrete suggestions

---

### 5. empirical

**Model**: Sonnet
**Phase**: 3 (Parallel Analysis)
**Input**: Chunks with tables/figures + surrounding text
**Output**: `agent_outputs/empirical.md`

**What it checks:**
- Text-to-table number cross-referencing (every number in text matches the table)
- Transposition errors (0.243 vs. 0.234)
- Sign errors (reporting a negative as positive)
- Magnitude errors (percentage vs. decimal)
- Statistical result consistency (coefficients, standard errors, p-values, significance stars)
- Cross-table consistency (sample sizes, repeated coefficients, variable definitions)
- Empirical specification consistency (do tables match the methodology description?)
- Figure-text consistency (do qualitative descriptions match what figures show?)
- Significance level consistency (do stars match stated significance levels?)

**How it works:**
1. First pass: understand the empirical strategy and variable definitions
2. Second pass: catalog every table and figure with key values
3. Third pass: go through text and cross-reference every number against tables/figures
4. Fourth pass: check cross-table consistency
5. Fifth pass: verify significance levels and statistical inference claims

**Common findings:**
- Text says "0.45" but table shows "0.54" (transposition)
- Text says "significant at 5%" but the t-statistic implies p > 0.05
- Sample size in Table 2 (N=1,234) does not match Table 4 (N=1,230) without explanation
- Model specification in text mentions "county fixed effects" but table header says "state FE"
- Rounding inconsistency: table shows 0.0456, text says "approximately 0.05"

**Limitations:**
- Cannot verify whether reported numbers are *correct* (e.g., whether the regression was run properly), only whether they are *internally consistent*
- Complex table layouts from PDF conversion may have formatting artefacts

---

### 6. cross-section

**Model**: Sonnet
**Phase**: 3 (Parallel Analysis)
**Input**: Pairs of related sections (intro+results, methods+results, abstract+conclusion)
**Output**: `agent_outputs/cross-section.md`

**What it checks:**
- Introduction vs. results: overclaiming, underclaiming, mischaracterisation
- Abstract vs. conclusion: consistency of claims, missing findings
- Methodology vs. results: methods described but never reported, results referencing undescribed methods
- Numbers/statistics that differ across sections
- Directional claims that flip (positive in intro, negative in results)
- Limitations vs. methodology alignment
- Literature review vs. own approach (criticising methods then using them)
- Contribution delivery (did the paper deliver what it promised?)

**How it works:**
For each section pair, the agent reads both sections side by side and systematically checks for contradictions, mismatches, and inconsistencies.

**Common findings:**
- Introduction claims "we find a positive effect" but the coefficient in the results is negative
- Abstract mentions four findings, conclusion discusses only three
- Methodology describes a robustness check that never appears in results
- Paper criticises OLS in the literature review but uses OLS itself
- Introduction promises "causal identification" but results section uses only correlational language

**Limitations:**
- Can only compare sections that are included in the same chunk pair
- Very subtle inconsistencies (e.g., a slight difference in how a finding is characterised) may be missed
- The severity assessment (HIGH/MEDIUM/LOW) maps to the standard classification (critical/major/minor)

---

### 7. econometrics

**Model**: Sonnet
**Phase**: 3 (Parallel Analysis)
**Input**: Methodology + results chunks
**Output**: `agent_outputs/econometrics.md`

**What it checks:**

**Identification strategy evaluation:**
- IV/2SLS: first-stage F-statistic, exclusion restriction plausibility, overidentification tests
- DID: parallel trends evidence, pre-trends testing, staggered adoption issues (TWFE bias), treatment effect heterogeneity
- RDD: bandwidth selection, McCrary density test, covariate balance, polynomial sensitivity
- Panel data: fixed effects specification, within/between variation, Hausman test, dynamic panel bias
- PSM: balance checks, common support, sensitivity analysis, matching method choice

**Standard errors:**
- Clustering level appropriateness
- Heteroskedasticity-robust standard errors
- Spatial correlation (Conley standard errors)
- Serial correlation
- Few-clusters problem (wild cluster bootstrap)

**Endogeneity:**
- Sources: omitted variable bias, reverse causality, measurement error
- Direction of bias (sign the bias where possible)

**Robustness:**
- Alternative specifications, sensitivity to functional form
- Placebo tests, falsification checks
- Coefficient stability (Oster, 2019)

**Common findings:**
- Standard TWFE estimator used with staggered adoption; should use Callaway and Sant'Anna (2021)
- Standard errors clustered at too low a level (individual when they should be at state level)
- No pre-trends test for DID despite claiming parallel trends
- Weak instrument (first-stage F < 10) without Anderson-Rubin inference
- Missing robustness to alternative bandwidth in RDD

**Limitations:**
- Evaluates methodology based on what is *described*; cannot verify the actual computational implementation
- For methods outside the economics/social science mainstream, the agent may lack specialised knowledge
- References to methodological literature use the anti-hallucination protocol: suggestions are marked as EXTERNAL KNOWLEDGE if not cited in the paper itself

---

### 8. literature

**Model**: Sonnet
**Phase**: 4 (Literature Search)
**Input**: Full literature review section + paper metadata
**Output**: `agent_outputs/literature.md`

**What it checks:**
- Coverage of major theoretical frameworks
- Presence of seminal/foundational papers
- Recency of cited literature (is the review up to date?)
- Coverage of methodological literature
- Clear positioning relative to existing work
- Contribution articulation
- For systematic reviews: search strategy, inclusion/exclusion criteria, PRISMA compliance

**How it works:**
1. Extract key terms, research question, and field from the paper
2. Use WebSearch to find potentially missing references
3. If Chrome is available, search Google Scholar with 3--5 key term combinations (3--8 second delays between searches)
4. Compare search results against the paper's bibliography
5. Use `verify_references.py` to confirm that suggested missing references actually exist

**Common findings:**
- Missing a seminal paper that any expert in the field would expect
- Literature review stops 5+ years before the paper's date
- Methodological literature not cited (e.g., the paper introducing the estimator used)
- Paper does not clearly position itself against the most relevant competing work

**Limitations:**
- Cannot assess the quality of how individual papers are discussed (only whether they are cited)
- Web search results are biased towards English-language publications
- Google Scholar search requires the Claude in Chrome extension
- **Critical rule**: Never fabricates a reference; only suggests papers that can be verified via API or web search

---

### 9. references

**Model**: Sonnet
**Phase**: 5 (Reference Verification)
**Input**: `_references.json` + verification script output
**Output**: `agent_outputs/references.md` + `verification/reference_report.json`

**What it checks:**
- Whether each reference exists in academic databases (CrossRef, OpenAlex, Semantic Scholar)
- Hallucination patterns: plausible but nonexistent titles, real authors with wrong papers, misspelled journals, invalid DOIs, impossible dates
- Citation completeness: every in-text citation has a reference list entry and vice versa
- Self-citation analysis: excessive self-citation without justification

**How it works:**
1. Load the `_references.json` extracted by the PDF parser
2. Run `verify_references.py` for programmatic three-tier API verification
3. Read the verification output (verified / suspicious / unverifiable per reference)
4. For unverifiable references, attempt web search as fallback
5. Interpret results and flag suspicious entries

**Common findings:**
- References that cannot be found in any database (potentially hallucinated by the paper's authors or by AI-assisted writing tools)
- DOI that does not resolve or resolves to a different paper
- Journal name that does not exist (e.g., "Journal of Economics Perspectives" instead of "Journal of Economic Perspectives")
- Year mismatch between the paper's citation and the API result
- Missing reference list entries for in-text citations

**Limitations:**
- Working papers, dissertations, and books may not be indexed in the databases, leading to false "unverifiable" results
- Non-English publications have lower coverage in all three APIs
- Very recent papers (published in the last few months) may not yet be indexed
- The PDF reference extraction is heuristic and may produce garbled entries for unusual formatting

---

### 10. language

**Model**: Sonnet
**Phase**: 3 (Parallel Analysis)
**Input**: All chunks in groups of 3--4
**Output**: `agent_outputs/language.md`

**What it checks:**

**English language evaluation:**
- Overall proficiency assessment (L1, L2, or L3 speaker)
- Common Central/Eastern European patterns: article misuse, preposition errors, word order issues, complex sentence structures, false friends (Hungarian/German)
- Passive voice overuse

**Academic register:**
- Appropriate formality for academic writing
- Disciplinary conventions (economics-specific phrasing)
- Colloquial or informal language

**Hungarian papers:**
- Hungarian academic register (tudományos stilus)
- Scientific terminology correctness (not calques from English)
- Grammar: suffixes, cases, verb conjugation (definite vs. indefinite)
- Stylistic conventions specific to Hungarian academic writing
- Findings produced in both English and Hungarian

**How it works:**
- Identifies systematic error patterns rather than cataloguing every individual error
- Provides representative examples (5--8) for each pattern type
- Focuses on errors that affect clarity and meaning over stylistic preferences
- Preserves the author's voice when suggesting corrections

**Common findings:**
- Systematic article omission ("We analyze impact of policy" instead of "the impact of the policy")
- Preposition errors transferred from L1 ("depend from" instead of "depend on")
- False friends: "actual" used to mean "current" (Hungarian/German transfer)
- Overly long, multi-clause sentences that obscure meaning
- For Hungarian papers: English calques where established Hungarian terminology exists

**Limitations:**
- Distinguishes language issues from content/logic issues; content issues are noted for the orchestrator but not analysed in depth
- Cannot assess whether field-specific jargon is used correctly (domain expertise is limited to general academic English conventions)
- Constructive in tone: focuses on patterns rather than exhaustive error listing

---

### 11. confidence-checker

**Model**: Opus
**Phase**: 6 (Confidence Iteration)
**Input**: All findings with confidence < 80% from Phases 3--5 + full paper Markdown
**Output**: `agent_outputs/confidence_check.md`

**What it does:**
Re-analyses findings that the original agents were not fully confident about. Uses the Opus model (the most capable) because this task requires the strongest reasoning to distinguish genuine issues from false positives.

**How it works:**
For each low-confidence finding:

1. **Expand context**: Read 500+ additional words before and after the passage
2. **Re-evaluate**: With expanded context, assess whether the finding is correct
3. **False positive check**: Is the issue addressed elsewhere (footnote, appendix, later section)? Is it an acceptable alternative in the field?
4. **Verdict**: CONFIRM (raise to 80%+), REVISE (modify the finding), or WITHDRAW (remove as false positive)

**Iteration rules:**
- Maximum 2 re-analysis iterations per finding
- After 2 iterations: confidence < 50% goes to Low-Confidence appendix
- After 2 iterations: confidence 50--79% gets a "moderate confidence" flag

**Quality standards:**
- Genuinely critical of original findings (the purpose is to reduce false positives)
- A good confidence check withdraws or revises a meaningful fraction of findings
- When in doubt, withdraw rather than confirm

**When it triggers:**
The confidence-checker runs whenever any finding from Phases 3--5 has a confidence score below 80%. If all findings are >= 80%, this phase is skipped.

**Common actions:**
- **Withdrawing** notation findings where the apparent inconsistency is actually a field-specific convention
- **Revising** exposition findings to reduce severity when expanded context clarifies the author's intent
- **Confirming** empirical cross-check findings when the discrepancy is verified with expanded context

**Limitations:**
- Limited to 2 iterations per finding to bound processing time
- Cannot access external APIs (relies on the paper text and existing agent outputs)
- The quality of the re-analysis depends on the quality of the original finding's evidence

---

### 12. precision-validator

**Model**: Opus
**Phase**: 8 (Precision Validation)
**Input**: Complete draft review + full paper Markdown + all verification data
**Output**: `verification/validation_report.json`

**What it does:**
The final quality gate before the review is published. Validates every single finding against the original paper to ensure nothing false or misrepresented reaches the author.

**How it works:**

**Tier A -- Internal Findings (95% precision threshold):**
1. Re-read the exact chunk of the paper that produced each finding
2. Verify that quoted text actually exists at the cited location
3. Verify that the finding accurately characterises what the paper says
4. Verify that suggested corrections are scientifically correct
5. Assign a precision probability (0--100%)
6. Iterate up to 3 times for findings below 95%
7. Downgrade to Low-Confidence appendix if still below 95% after 3 iterations

**Tier B -- External Findings (85--90% precision threshold):**
1. Re-check the API or search result that produced the finding
2. Verify the database result matches the claim
3. Accept at >= 90%, flag with "moderate confidence" at 85--90%, iterate or downgrade below 85%
4. Time-limited to 15 minutes total for all Tier B findings

**Holistic validation:**
1. Logical consistency: does the recommendation follow from the findings?
2. Recommendation calibration: does severity match the recommendation?
3. Tone consistency: is the review consistently constructive and professional?
4. Internal contradictions: does the review contradict itself?
5. Completeness: has any major section of the paper been overlooked?

**Output format:**
- Per-finding: `{ finding_id, tier, precision_score, status, iterations, confidence_flag, notes }`
- Summary: `validation_report.json` with counts per tier and holistic check results
- Overall status: `READY_FOR_PUBLICATION` or `NEEDS_REVISION`

**Limitations:**
- Tier B is time-bounded (15 minutes), so not all external findings may receive thorough re-verification
- Cannot detect issues that no agent found in the first place (it validates existing findings, not discovers new ones)
- The holistic check is qualitative and relies on the model's judgment about consistency and tone

---

## Agent Interactions

### How Findings from One Agent Can Inform Another

While agents run independently during Phase 3, their findings are combined during later phases:

| Upstream Agent | Downstream Consumer | How Findings Are Used |
|---|---|---|
| math-logic | precision-validator | Equation corrections are re-verified for mathematical correctness |
| notation | exposition | Symbol inconsistencies may explain unclear passages |
| empirical | cross-section | Number discrepancies between text and tables feed into cross-section consistency checks |
| econometrics | exposition | Methodology issues may explain why the results section is confusing |
| literature | references | Missing references from literature search are checked for existence by the references agent |
| All agents | confidence-checker | Any finding below 80% confidence is re-analysed |
| All agents | precision-validator | Every finding is re-verified against the paper |

### Information Shared Across Agents

All agents receive:
- The path to the converted Markdown file
- The `chunk_map.json` with their assigned chunks
- The abstract + introduction text (for context)
- The anti-hallucination guardrails (`.claude/rules/no-hallucination.md`)
- The review standards (`.claude/rules/review-standards.md`)

---

## Confidence Scoring

### How Each Agent Assigns Scores

All agents follow the same confidence scale defined in the anti-hallucination guardrails:

| Range | Meaning | Typical Evidence |
|---|---|---|
| 90--100% | Clear, unambiguous error with direct evidence | Exact quote showing the error; correction is straightforward |
| 70--89% | Likely error, strong but not conclusive evidence | Quote suggests an error but an alternative interpretation exists |
| 50--69% | Possible issue, requires author clarification | The text is ambiguous; the issue depends on the author's intent |
| Below 50% | Uncertain; flag only if potentially important | Suspicion based on pattern matching rather than direct evidence |

### Confidence Thresholds in the Pipeline

| Threshold | Where Applied | Action |
|---|---|---|
| < 80% | After Phase 3 | Finding is sent to the confidence-checker for re-analysis |
| < 50% after 2 iterations | Confidence-checker | Finding is moved to Low-Confidence appendix |
| < 95% (Tier A) | Precision-validator | Finding is flagged for revision; up to 3 iterations |
| < 85% (Tier B) | Precision-validator | Finding is iterated once; if still < 85%, downgraded |

---

## Anti-Hallucination Enforcement

All agents are bound by the rules in `.claude/rules/no-hallucination.md`:

1. Only reference content that exists in the document
2. Quote exact text when identifying issues (block-quote format)
3. Never infer external facts; only check internal consistency
4. Exception: literature and references agents may use external sources
5. Assign confidence scores to every finding
6. Cite section name + page number for every finding
7. When uncertain, say "I could not verify this" rather than guessing
8. Never fabricate a citation, equation, or claim
9. External knowledge must be disclosed and marked as EXTERNAL KNOWLEDGE
10. Only suggest corrections you are confident are scientifically correct

Violations of these guardrails result in findings being discarded rather than reported with low confidence.
