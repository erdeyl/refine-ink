# Setup Guide

Step-by-step instructions for installing and configuring refine-ink.

---

## Prerequisites

Before you begin, ensure you have the following installed:

| Requirement | Version | How to Check |
|---|---|---|
| **Python** | 3.10 or later | `python3 --version` |
| **pip** | Latest | `pip --version` |
| **Claude Code** | Latest | `claude --version` |
| **git** | Any recent version | `git --version` |

Optional but recommended:

| Requirement | Purpose | How to Get |
|---|---|---|
| **Claude in Chrome extension** | Enables Google Scholar searches during literature review | Install from the Chrome Web Store |
| **Semantic Scholar API key** | Higher rate limits for reference verification | Free at [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api) |

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/erdeyl/refine-ink.git
cd refine-ink
```

---

## Step 2: Install Python Dependencies

```bash
pip install -r scripts/requirements.txt
```

This installs:

| Package | Version | Purpose |
|---|---|---|
| `pymupdf4llm` | >= 0.0.17 | PDF-to-Markdown conversion with multi-column layout handling |
| `httpx` | >= 0.27.0 | Async HTTP client for API calls (reference verification) |
| `markdown` | >= 3.7 | Markdown-to-HTML conversion for review output |
| `jinja2` | >= 3.1.4 | HTML templating for styled review output |
| `nh3` | >= 0.2.17 | Preferred HTML sanitization backend for safe report rendering |
| `bleach` | >= 6.1.0 | Fallback HTML sanitization backend if `nh3` is unavailable |

Note: `pymupdf4llm` automatically installs `pymupdf` (PyMuPDF/fitz) as a dependency, which handles low-level PDF operations.

---

## Step 3: (Optional) Semantic Scholar API Key

The reference verification script works without an API key, but authenticated requests get higher rate limits (100 requests/second vs. 5 requests/second).

1. Go to [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api)
2. Sign up for a free API key
3. Set the environment variable:

```bash
# Add to your shell profile (.zshrc, .bashrc, etc.)
export S2_API_KEY="your_api_key_here"
```

Alternatively, you can pass the key directly when running the verification script:

```bash
python scripts/verify_references.py refs.json --s2-api-key your_key_here
```

---

## Step 4: (Optional) Claude in Chrome Extension

The Claude in Chrome extension enables browser-based Google Scholar searches during the literature review phase. Without it, the system falls back to web search only.

1. Install the Claude in Chrome extension from the Chrome Web Store
2. Ensure Chrome is running when you start a review
3. The `/review` skill will automatically detect and use the extension if available

---

## Step 5: Verify Installation

Run these commands to verify that all components are working:

```bash
# Check PDF conversion script
python scripts/pdf_to_markdown.py --help

# Check conversion verification script
python scripts/verify_conversion.py --help

# Check reference verification script
python scripts/verify_references.py --help

# Check that pymupdf4llm is installed correctly
python3 -c "import pymupdf4llm; print('pymupdf4llm version:', pymupdf4llm.__version__)"

# Check that httpx is installed
python3 -c "import httpx; print('httpx version:', httpx.__version__)"
```

All commands should complete without errors.

---

## Step 6: Configuration

### `.claude/settings.json`

This file controls which tools the agents are permitted to use. The default configuration is pre-set for the review workflow and should not need modification for normal use.

Key permissions:

```json
{
  "permissions": {
    "allow": [
      "Bash(python scripts/pdf_to_markdown.py*)",
      "Bash(python scripts/verify_conversion.py*)",
      "Bash(python scripts/verify_references.py*)",
      "Bash(python scripts/md_to_html.py*)",
      "Read",
      "Write(reviews/**)",
      "Glob",
      "Grep",
      "WebSearch",
      "WebFetch"
    ],
    "deny": [
      "Bash(rm -rf*)",
      "Bash(git push*)"
    ]
  }
}
```

### `.claude/settings.local.json`

For local overrides (API keys, additional permissions, custom domains for WebFetch), edit this file. It is not tracked by git.

### Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `S2_API_KEY` | No | Semantic Scholar API key for higher rate limits |

---

## Step 7: First Review

Open Claude Code in the project directory and run:

```
/review path/to/paper.pdf
```

The system will:

1. Convert the PDF to Markdown
2. Verify the conversion quality
3. Chunk the paper for analysis
4. Launch 7 analysis agents in parallel
5. Search for missing literature
6. Verify all references via APIs
7. Re-analyse low-confidence findings
8. Synthesise the referee report
9. Validate every finding for precision
10. Generate Markdown + HTML output

Progress is reported after each phase.

---

## Troubleshooting

### PDF conversion fails

- Ensure the PDF is not encrypted or password-protected
- Ensure `pymupdf4llm` is installed: `pip install pymupdf4llm`
- Try updating: `pip install --upgrade pymupdf4llm pymupdf`
- Some heavily image-based PDFs (scanned documents) will produce poor results; the system works best with text-based PDFs

### Reference verification times out

- This is usually caused by rate limiting. The script uses exponential backoff and retries automatically.
- If you have many references (50+), the verification phase may take 5--10 minutes.
- Adding a Semantic Scholar API key significantly improves throughput.

### Conversion verification reports FAIL

- Read the verification report to understand which checks failed.
- Common causes: multi-column layouts that confuse the parser, tables rendered as images, heavy use of footnotes.
- You can inspect the converted Markdown file directly and make manual corrections before proceeding.

### Claude in Chrome not detected

- Ensure Chrome is running and the extension is active.
- The extension must be connected to the same Claude Code session.
- If unavailable, the system will skip Google Scholar searches and rely on WebSearch only.

### Permission errors

- Ensure `.claude/settings.json` has the correct `allow` entries for the scripts you need to run.
- Check that the `reviews/` directory is writable.
