# refine-ink -- AI-Powered Scientific Paper Review System

> Emulates [Refine.ink](https://refine.ink)'s approach to producing top-journal-quality referee reports using Claude Code's agent system.

<!-- Badges -->
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-blueviolet.svg)
![Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange.svg)

---

## Features

- **Multi-pass parallelised analysis** -- 12 specialised agents review a paper simultaneously across orthogonal quality dimensions
- **Reference validation** -- three-tier cascade using CrossRef, OpenAlex, and Semantic Scholar APIs with fuzzy title matching
- **Hallucination detection** -- identifies fabricated citations, nonexistent journals, and impossible DOIs
- **Confidence scoring with iteration** -- every finding is rated 0--100%; low-confidence findings are re-analysed by a dedicated Opus-class agent
- **Precision validation** -- a final quality gate re-verifies every finding against the original paper before publication
- **Econometric method evaluation** -- deep assessment of identification strategies, standard errors, endogeneity, and robustness
- **L2/L3 English support** -- specialised language evaluation tuned for Central/Eastern European academic English patterns
- **Hungarian language support** -- full Hungarian academic register review; dual-language output for Hungarian papers
- **PhD dissertation support** -- chapter-by-chapter analysis with cross-chapter consistency checks
- **Audit trail** -- every review produces a `manifest.json` with full traceability from PDF input to final report
- **Styled HTML output** -- publication-ready HTML alongside Markdown, using a serif academic template

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/erdeyl/refine-ink.git
cd refine-ink

# 2. Install Python dependencies
pip install -r scripts/requirements.txt

# 3. Review a paper (inside Claude Code)
/review path/to/paper.pdf
```

The `/review` command launches the full multi-agent pipeline. A typical journal article (20--40 pages) takes 15--30 minutes; a PhD dissertation may take 60--90 minutes.

---

## Architecture Overview

refine-ink uses Claude Code's agent system to orchestrate 12 specialised review agents that run in parallel. Each agent analyses a different quality dimension of the paper, and their findings are then iteratively validated before synthesis into a coherent referee report.

### Agent Table

| Agent | Model | Purpose |
|---|---|---|
| **paper-parser** | Haiku | Parses converted markdown into analysis-ready chunks |
| **math-logic** | Sonnet | Verifies equations, derivations, proofs, and logical reasoning |
| **notation** | Sonnet | Checks symbol, variable, and acronym consistency |
| **exposition** | Sonnet | Evaluates argument flow, clarity, and structural coherence |
| **empirical** | Sonnet | Cross-checks tables, figures, and numbers against text |
| **cross-section** | Sonnet | Detects contradictions between different paper sections |
| **econometrics** | Sonnet | Evaluates statistical and econometric methodology |
| **literature** | Sonnet | Assesses literature review coverage and gap identification |
| **references** | Sonnet | Validates references and detects hallucinated citations |
| **language** | Sonnet | Evaluates language quality for L2/L3 English and Hungarian |
| **confidence-checker** | Opus | Re-verifies low-confidence findings from all other agents |
| **precision-validator** | Opus | Final quality gate: validates every finding against the paper |

---

## How It Works

```
PDF Input
   |
   v
[Phase 0]  Setup (locate PDF, create review directory)
   |
   v
[Phase 1]  PDF --> Markdown conversion (pymupdf4llm)
   |          + conversion verification (word count, sections, tables, spot checks)
   v
[Phase 2]  Chunking (dimension-specific sizes, 150--200 word overlap)
   |
   v
[Phase 3]  Parallel Analysis (7 agents run simultaneously; 3x in triple-workflow mode)
   |          math-logic | notation | exposition | empirical
   |          cross-section | econometrics | language
   v
[Phase 4]  Literature Search (WebSearch + Google Scholar via Chrome)
   |
   v
[Phase 5]  Reference Verification (CrossRef -> OpenAlex -> Semantic Scholar cascade)
   |
   v
[Phase 6]  Cross-Workflow Synthesis (triple-workflow mode: merge 3 finding sets)
   |
   v
[Phase 7]  Confidence Iteration (Opus re-analyses findings < 80% confidence)
   |
   v
[Phase 8]  Synthesis (aggregate findings into structured referee report)
   |
   v
[Phase 9]  Precision Validation (Opus validates every finding against the paper)
   |          Tier A: internal findings, 95% precision threshold
   |          Tier B: external findings, 85--90% threshold
   v
[Phase 10] Output Generation (Markdown + HTML, English + Hungarian if applicable)
```

---

## Output Format

Each review produces a structured referee report containing:

1. **Summary** -- 1--2 paragraph overview of the paper
2. **Overall Assessment** -- strengths, concerns, and recommendation
3. **Major Comments** -- substantive issues with verbatim corrections
4. **Minor Comments** -- notation, clarity, and presentation issues
5. **Econometric/Statistical Methodology** -- dedicated methodology assessment
6. **Data Quality and Measurement** -- data definitions, harmonisation, coverage consistency
7. **Literature and References** -- coverage gaps + verification summary
8. **Language and Presentation** -- constructive language suggestions
9. **Suggestions for Improvement** -- optional enhancements
10. **Appendices** -- detailed findings table, low-confidence findings, methodology notes

**Output files:**
- `review_EN.md` + `review_EN.html` -- English review
- `review_HU.md` + `review_HU.html` -- Hungarian review (for Hungarian papers)
- `manifest.json` -- full audit trail

---

## Supported Fields

- Economics (micro, macro, labour, development, trade, public finance)
- Business and management
- Development studies
- Social sciences broadly (with strongest coverage in quantitative empirical work)

The system is calibrated to the quality expectations of top-ranked journals: AER, QJE, Econometrica, JFE, REStat, JOLE, JDE.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Required for PDF conversion and reference verification scripts |
| Claude Code | Latest | The CLI that orchestrates the agent system |
| Claude in Chrome extension | Latest | *Optional.* Enables Google Scholar searches during literature review |
| Semantic Scholar API key | Free | *Optional.* Higher rate limits for reference verification |

---

## Configuration

### `.claude/settings.json`

Controls which tools the agents are permitted to use. The default configuration allows:

- Running all Python scripts in `scripts/`
- Reading and writing to `reviews/` and `output/`
- Web search and web fetch for literature and reference verification
- File system operations (read, glob, grep)

### Semantic Scholar API Key

For higher rate limits during reference verification, obtain a free API key at [semanticscholar.org](https://www.semanticscholar.org/product/api) and either:

- Set the environment variable: `export S2_API_KEY=your_key_here`
- Pass it directly: `python scripts/verify_references.py refs.json --s2-api-key your_key_here`

---

## Project Structure

```
refine-ink/
  .claude/
    agents/               # Agent definitions (one directory per agent)
      math-logic/
      notation/
      exposition/
      empirical/
      cross-section/
      econometrics/
      literature/
      references/
      language/
      confidence-checker/
      precision-validator/
      paper-parser/
    rules/                # Shared rules enforced across all agents
      no-hallucination.md
      review-standards.md
      statistical-pitfalls.md
    skills/
      review/SKILL.md     # The /review skill orchestrator
    settings.json         # Permissions and tool configuration
  scripts/
    pdf_to_markdown.py    # PDF to Markdown conversion
    verify_conversion.py  # Conversion fidelity verification
    pdf_section_map.py    # PDF heading → page-range mapping
    verify_references.py  # Reference validation via APIs
    md_to_html.py         # Markdown to styled HTML
    review_template.html  # HTML template for output
    requirements.txt      # Python dependencies
  docs/                   # Detailed documentation
  reviews/                # Generated reviews (gitignored)
  CLAUDE.md               # Project context for Claude Code
  README.md               # This file
```

---

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

- [**ARCHITECTURE.md**](docs/ARCHITECTURE.md) -- System architecture, data flow, and agent interactions
- [**SETUP.md**](docs/SETUP.md) -- Step-by-step installation and configuration guide
- [**USAGE.md**](docs/USAGE.md) -- How to use the system and interpret output
- [**AUDIT.md**](docs/AUDIT.md) -- Audit trail format and verification procedures
- [**CHUNKING.md**](docs/CHUNKING.md) -- Chunking strategy rationale and dimension-specific sizes
- [**AGENTS.md**](docs/AGENTS.md) -- Detailed documentation of all 12 agents

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Credits

Inspired by [Refine.ink](https://refine.ink) -- an AI-powered scientific paper review service.

Built with [Claude Code](https://claude.ai/claude-code) by Anthropic.
