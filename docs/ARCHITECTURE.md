# Architecture

This document describes the system architecture of refine-ink, including data flow, agent design, chunking strategy, API integrations, and file structure.

---

## System Diagram

```
                              +-------------------+
                              |   PDF Input File   |
                              +--------+----------+
                                       |
                              [Phase 1: Conversion]
                                       |
                          +------------+------------+
                          |                         |
                   pdf_to_markdown.py        verify_conversion.py
                          |                         |
                          v                         v
                  _converted.md              verification report
                  _references.json           (PASS / WARN / FAIL)
                          |
                 [Phase 2: Chunking]
                          |
                          v
                   chunk_map.json
                   (dimension-specific
                    chunk assignments)
                          |
            +-------------+-------------+
            |             |             |
     [Phase 3: Parallel Analysis]       |
            |             |             |
     +------+------+  +--+---+  +------+------+
     | math-logic  |  |notat.|  | exposition  |
     | empirical   |  |cross-|  | econometrics|
     | language    |  |section|  |             |
     +------+------+  +--+---+  +------+------+
            |             |             |
            +------+------+------+------+
                   |
          [Phase 4: Literature Search]
                   |
                   v
          WebSearch + Google Scholar
          (via Claude in Chrome)
                   |
          [Phase 5: Reference Verification]
                   |
                   v
          verify_references.py
          CrossRef -> OpenAlex -> Semantic Scholar
                   |
          [Phase 6: Confidence Iteration]
                   |
                   v
          confidence-checker (Opus)
          Re-analyse findings < 80%
                   |
          [Phase 7: Synthesis]
                   |
                   v
          Draft referee report
                   |
          [Phase 8: Precision Validation]
                   |
                   v
          precision-validator (Opus)
          Tier A: 95% threshold (internal)
          Tier B: 85-90% threshold (external)
                   |
          [Phase 9: Output]
                   |
          +--------+--------+
          |        |        |
      review_EN  review_HU  manifest.json
      (.md/.html) (.md/.html)  (audit trail)
```

---

## Agent Architecture

### Agent Definition Structure

Each agent is defined as a Markdown file in `.claude/agents/<agent-name>/<agent-name>.md` with YAML front matter:

```yaml
---
name: agent-name
description: What this agent does
tools: Read, Grep, Glob       # Tools the agent can use
model: sonnet                  # Model tier: haiku, sonnet, or opus
---
```

The body of the file contains the agent's detailed instructions, scope of review, output format, and workflow.

### Agent Descriptions

| Agent | Model | Tools | Chunk Size | Purpose |
|---|---|---|---|---|
| paper-parser | Haiku | Read, Grep, Glob, Bash, Write | Full document | Parses converted markdown into dimension-specific chunks |
| math-logic | Sonnet | Read, Grep, Glob | 800--1,200 words | Verifies equations, derivations, proofs, logical reasoning |
| notation | Sonnet | Read, Grep, Glob | 800--1,200 words (groups of 3--4) | Checks symbol/variable/acronym consistency |
| exposition | Sonnet | Read, Grep, Glob | 1,500--2,500 words (groups of 3--4) | Evaluates argument flow, clarity, structural coherence |
| empirical | Sonnet | Read, Grep, Glob | 1,000--1,500 words | Cross-checks tables/figures/numbers against text claims |
| cross-section | Sonnet | Read, Grep, Glob | 2,000--3,000 words (paired) | Detects contradictions between different paper sections |
| econometrics | Sonnet | Read, Grep, Glob | 1,200--1,800 words | Evaluates econometric methodology: ID strategy, SE, robustness |
| literature | Sonnet | Read, Grep, Glob, WebSearch, Bash | Full section | Assesses literature review coverage and identifies gaps |
| references | Sonnet | Read, Grep, Glob, Bash, WebSearch | 15--20 refs per batch | Validates references via APIs and detects hallucinated citations |
| language | Sonnet | Read, Grep, Glob | 1,500--2,000 words (groups of 3--4) | Evaluates L2/L3 English quality and Hungarian academic register |
| confidence-checker | Opus | Read, Grep, Glob | Variable (expanded context) | Re-verifies findings with confidence < 80% |
| precision-validator | Opus | Read, Grep, Glob | Variable | Final quality gate: validates every finding against the paper |

### Model Selection Rationale

- **Haiku**: Used only for the paper-parser, a structured parsing task that does not require deep reasoning.
- **Sonnet**: Used for the seven analysis agents. These require expert-level domain knowledge but process bounded chunks, making Sonnet's capability-to-speed ratio optimal.
- **Opus**: Reserved for the confidence-checker and precision-validator, which require the strongest reasoning capabilities to detect false positives, re-evaluate ambiguous findings, and perform holistic review validation.

---

## Chunking Strategy

The paper is split into chunks of different sizes depending on which agent will analyse them. The rationale is that different review dimensions require different levels of context:

| Dimension | Target Size | Rationale |
|---|---|---|
| math-logic | 800--1,200 words | Every token gets strong attention; equations need focused verification |
| notation | 800--1,200 words | Symbol tracking requires careful per-token analysis |
| empirical | 1,000--1,500 words | Tables + surrounding discussion need to fit together |
| exposition | 1,500--2,500 words | Argument flow requires broader context to evaluate transitions |
| cross-section | 2,000--3,000 words (paired) | Comparing two sections requires both to be present |
| econometrics | 1,200--1,800 words | Methods + results need enough context for assessment |
| literature | Full section | The literature review must be analysed as a whole |
| references | 15--20 refs per batch | Batch size for efficient API verification |
| language | 1,500--2,000 words | Language patterns need enough text to detect systematic issues |

Chunks overlap by 150--200 words to maintain context continuity across boundaries.

For detailed rationale, see [CHUNKING.md](CHUNKING.md).

---

## API Integration

### CrossRef

- **Purpose**: Primary reference verification
- **Endpoint**: `https://api.crossref.org/works`
- **Lookup methods**: DOI resolution, bibliographic title search
- **Rate limit**: 10 requests/second (polite pool with email)
- **Authentication**: None required; `mailto` parameter recommended for polite pool access

### OpenAlex

- **Purpose**: Secondary reference verification (broader coverage, including books and working papers)
- **Endpoint**: `https://api.openalex.org/works`
- **Lookup methods**: DOI resolution, title search
- **Rate limit**: 10 requests/second (polite pool with email)
- **Authentication**: None required; `mailto` parameter recommended

### Semantic Scholar

- **Purpose**: Tertiary reference verification (strong coverage of computer science and social sciences)
- **Endpoint**: `https://api.semanticscholar.org/graph/v1/paper`
- **Lookup methods**: DOI resolution, title search
- **Rate limit**: 5 requests/second unauthenticated; higher with API key
- **Authentication**: Optional API key via `S2_API_KEY` environment variable or `--s2-api-key` flag

### Google Scholar (via Claude in Chrome)

- **Purpose**: Literature gap identification and supplementary reference searches
- **Access**: Browser automation through Claude in Chrome extension MCP tools
- **Rate limiting**: 3--8 second random delays between searches to avoid detection
- **Authentication**: None (uses the browser's normal session)

### Verification Cascade

References are verified using a three-tier cascade with early exit:

```
Reference --> CrossRef (DOI, then title search)
                |
                +--> Match >= 85% similarity? --> VERIFIED (exit)
                |
                +--> OpenAlex (DOI, then title search)
                       |
                       +--> Match >= 85%? --> VERIFIED (exit)
                       |
                       +--> Semantic Scholar (DOI, then title search)
                              |
                              +--> Match >= 85%? --> VERIFIED (exit)
                              |
                              +--> 70-85%? --> SUSPICIOUS
                              +--> < 70%? --> UNVERIFIABLE
```

---

## File Structure

### Review Directory

Each review creates the following directory structure under `reviews/`:

```
reviews/[paper_name]_[YYYY-MM-DD]/
  input/
    original.pdf              # Copy of the input PDF
    [name]_converted.md       # Markdown conversion output
    [name]_references.json    # Extracted structured references
  verification/
    [name]_verification.json  # Conversion verification report
    reference_report.json     # Reference verification results
    validation_report.json    # Precision validation results
  chunks/
    chunk_map.json            # Chunk boundaries and dimension assignments
  agent_outputs/
    math-logic.md             # Findings from each agent
    notation.md
    exposition.md
    empirical.md
    cross-section.md
    econometrics.md
    literature.md
    references.md
    language.md
    confidence_check.md
  output/
    review_EN.md              # Final English review (Markdown)
    review_EN.html            # Final English review (HTML)
    review_HU.md              # Hungarian review (if applicable)
    review_HU.html            # Hungarian review (if applicable)
    manifest.json             # Full audit trail
```

### Configuration Files

| File | Purpose |
|---|---|
| `.claude/settings.json` | Global tool permissions (allow/deny lists) |
| `.claude/settings.local.json` | Local overrides (API keys, custom permissions) |
| `.claude/rules/no-hallucination.md` | Anti-hallucination guardrails enforced across all agents |
| `.claude/rules/review-standards.md` | Severity classification, correction format, writing standards |
| `.claude/skills/review/SKILL.md` | The `/review` skill orchestrator (9-phase workflow) |

---

## Data Flow

### Finding Propagation

```
Agent produces finding
  |
  +--> finding_text, severity, confidence, evidence, location, correction
  |
  +--> Saved to agent_outputs/[agent].md
  |
  v
Confidence < 80%?
  |
  YES --> confidence-checker re-analyses with expanded context
  |         |
  |         +--> CONFIRM (raise to 80%+)
  |         +--> REVISE (modify finding)
  |         +--> WITHDRAW (remove false positive)
  |
  NO --> Pass through to synthesis
  |
  v
Synthesis: aggregate all validated findings into referee report
  |
  v
Precision validator checks EVERY finding against paper
  |
  +--> Tier A (internal): 95% precision threshold, up to 3 iterations
  +--> Tier B (external): 85-90% threshold, 15-minute time limit
  |
  +--> Below threshold after max iterations? --> Low-Confidence Appendix
  |
  v
Final report
```

### Severity Classification

All agents use a unified severity scale calibrated to top economics journals:

| Severity | Meaning | Impact |
|---|---|---|
| Critical | Invalidates results or contains fundamental logical flaws | Likely drives a reject or major revision recommendation |
| Major | Could change conclusions; significant methodological concerns | Contributes to major revision recommendation |
| Minor | Does not affect results; notation, clarity, or presentation issues | Contributes to minor revision recommendation |
| Suggestion | Optional improvements or alternative approaches | Does not affect recommendation |
