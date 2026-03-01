# Refine-Ink: Scientific Paper Review System

This project emulates Refine.ink's approach to AI-powered scientific paper review, producing top-journal-quality referee reports for social science papers.

## Quick Start

To review a paper: `/review path/to/paper.pdf`

## How It Works

The system uses parallelized multi-pass analysis with 11 specialized agents, each analyzing a different dimension of the paper. All analysis is grounded in the document text to prevent hallucination.

## Key Principles

1. **No hallucination**: Every claim must cite exact text from the paper. See @.claude/rules/no-hallucination.md
2. **Verbatim corrections**: Every error includes a specific fix. See @.claude/rules/review-standards.md
3. **Assertion-style titles**: Every finding title states a conclusion, not a vague label. See @.claude/rules/review-standards.md
4. **Design before results**: Evaluate research design validity BEFORE examining results to prevent anchoring bias. See @.claude/rules/review-standards.md
5. **Human-like prose**: Write as a senior reviewer at AER/QJE, not as an AI
6. **Confidence scores**: Every finding rated 0-100%, iterated if below thresholds
7. **Statistical awareness**: Be alert to common pitfalls, biases, and fallacies. See @.claude/rules/statistical-pitfalls.md
8. **Audit trail**: Every review produces a manifest.json for full traceability
9. **Read-only input**: Never modify the original paper files in `reviews/*/input/`

## Review Agents

| Agent | Purpose | Model |
|-------|---------|-------|
| math-logic | Equations, proofs, derivations | Sonnet |
| notation | Symbol/variable consistency | Sonnet |
| exposition | Argument flow, clarity | Sonnet |
| empirical | Tables/figures vs text | Sonnet |
| cross-section | Inter-section consistency | Sonnet |
| econometrics | Statistical methods | Sonnet |
| literature | Literature review coverage | Sonnet |
| references | Reference validation + hallucination detection | Sonnet |
| language | L2/L3 English + Hungarian | Sonnet |
| confidence-checker | Re-verify low-confidence findings | Opus |
| precision-validator | Final review↔paper validation | Opus |

## Supported Input

- **PDF files** of academic papers and PhD dissertations
- **Languages**: English, Hungarian
- **Fields**: Economics, business, development studies, social sciences

## Output

- Markdown + HTML referee report
- For Hungarian papers: both English and Hungarian versions
- Full audit trail in manifest.json

## Scripts

- `scripts/pdf_to_markdown.py` — PDF → Markdown conversion
- `scripts/verify_conversion.py` — Verify conversion fidelity
- `scripts/verify_references.py` — Validate references via CrossRef/OpenAlex/Semantic Scholar
- `scripts/md_to_html.py` — Convert review to styled HTML

## Setup

```bash
pip install -r scripts/requirements.txt
```
