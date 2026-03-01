# Audit Trail

This document explains the audit trail produced by every refine-ink review, including the `manifest.json` format, how to verify a review, how to reproduce it, and what the audit trail proves.

---

## Purpose

The audit trail exists for three reasons:

1. **Reproducibility** -- Given the same PDF and system version, the review process can be repeated and results compared.
2. **Traceability** -- Every finding in the final review can be traced back through the pipeline to the specific chunk of text, the agent that produced it, the confidence iteration results, and the precision validation outcome.
3. **Accountability** -- The audit trail documents what the system checked, what it found, what it could not verify, and what decisions were made about borderline findings.

---

## manifest.json Format

The `manifest.json` file is written to `reviews/[name]/output/manifest.json` at the end of every review. Below is a description of every field.

### Top-Level Fields

```json
{
  "version": "1.0",
  "generated_at": "2025-01-15T14:32:00Z",
  "duration_minutes": 22.5,
  "system": { ... },
  "paper": { ... },
  "conversion": { ... },
  "chunking": { ... },
  "agents": { ... },
  "reference_verification": { ... },
  "confidence_iteration": { ... },
  "precision_validation": { ... },
  "findings_summary": { ... },
  "recommendation": "Major Revisions"
}
```

| Field | Type | Description |
|---|---|---|
| `version` | string | Manifest format version |
| `generated_at` | string (ISO 8601) | Timestamp when the review completed |
| `duration_minutes` | number | Total wall-clock time for the review |
| `system` | object | System configuration details |
| `paper` | object | Paper metadata extracted during processing |
| `conversion` | object | PDF-to-Markdown conversion results |
| `chunking` | object | Chunking statistics |
| `agents` | object | Per-agent execution statistics |
| `reference_verification` | object | Reference verification summary |
| `confidence_iteration` | object | Confidence checker results |
| `precision_validation` | object | Precision validator results |
| `findings_summary` | object | Final findings counts by severity |
| `recommendation` | string | Overall recommendation |

### `system` Object

```json
{
  "system": {
    "orchestrator": "review/SKILL.md",
    "agents_used": [
      "paper-parser", "math-logic", "notation", "exposition",
      "empirical", "cross-section", "econometrics", "literature",
      "references", "language", "confidence-checker", "precision-validator"
    ],
    "rules_applied": [
      "no-hallucination.md",
      "review-standards.md"
    ],
    "tools_available": ["Read", "Write", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"],
    "chrome_extension_available": true
  }
}
```

### `paper` Object

```json
{
  "paper": {
    "title": "The Effect of Trade Policy on Firm Innovation",
    "language": "en",
    "document_type": "article",
    "pages": 42,
    "words": 12500,
    "sections": 7,
    "tables": 8,
    "figures": 4,
    "references_count": 67,
    "input_path": "reviews/trade_policy_2025-01-15/input/original.pdf"
  }
}
```

### `conversion` Object

```json
{
  "conversion": {
    "status": "PASS",
    "pdf_word_count": 12500,
    "md_word_count": 12380,
    "word_count_diff_pct": 0.96,
    "sections_pdf": 7,
    "sections_md": 7,
    "tables_pdf": 8,
    "tables_md": 8,
    "spot_check_hits": 20,
    "spot_check_total": 20,
    "warnings": [],
    "failures": []
  }
}
```

### `chunking` Object

```json
{
  "chunking": {
    "total_chunks": 18,
    "average_chunk_words": 694,
    "dimension_assignments": {
      "math-logic": 5,
      "notation": 6,
      "exposition": 6,
      "empirical": 4,
      "cross-section": 3,
      "econometrics": 4,
      "literature": 1,
      "references": 1,
      "language": 6
    }
  }
}
```

### `agents` Object

```json
{
  "agents": {
    "math-logic": {
      "model": "sonnet",
      "chunks_processed": 5,
      "findings_produced": 3,
      "by_severity": {"critical": 0, "major": 1, "minor": 2, "suggestion": 0},
      "average_confidence": 87.3,
      "duration_seconds": 45
    },
    "notation": { ... },
    "exposition": { ... },
    "empirical": { ... },
    "cross-section": { ... },
    "econometrics": { ... },
    "literature": { ... },
    "references": { ... },
    "language": { ... }
  }
}
```

### `reference_verification` Object

```json
{
  "reference_verification": {
    "total": 67,
    "verified": 58,
    "suspicious": 3,
    "unverifiable": 6,
    "apis_used": ["crossref", "openalex", "semantic_scholar"],
    "web_search_fallbacks": 4,
    "google_scholar_used": true
  }
}
```

### `confidence_iteration` Object

```json
{
  "confidence_iteration": {
    "findings_reviewed": 8,
    "confirmed": 5,
    "revised": 2,
    "withdrawn": 1,
    "moved_to_low_confidence": 0,
    "model": "opus"
  }
}
```

### `precision_validation` Object

```json
{
  "precision_validation": {
    "tier_a": {
      "total": 30,
      "accepted": 27,
      "flagged_for_revision": 2,
      "downgraded_to_low_confidence": 1
    },
    "tier_b": {
      "total": 12,
      "accepted": 9,
      "accepted_moderate_confidence": 2,
      "downgraded_to_low_confidence": 1
    },
    "holistic": {
      "logical_consistency": "PASS",
      "recommendation_calibration": "PASS",
      "tone_consistency": "PASS",
      "internal_contradictions": "PASS",
      "completeness": "PASS"
    },
    "overall_status": "READY_FOR_PUBLICATION",
    "average_precision": 94.2,
    "model": "opus"
  }
}
```

### `findings_summary` Object

```json
{
  "findings_summary": {
    "total": 42,
    "critical": 1,
    "major": 7,
    "minor": 22,
    "suggestion": 12,
    "low_confidence_appendix": 3
  }
}
```

---

## How to Verify a Review

Given a completed review, you can verify its integrity and trace its findings as follows:

### 1. Check the Manifest

Read `output/manifest.json` and verify:

- The conversion status is PASS or WARN (not FAIL)
- The precision validation overall status is READY_FOR_PUBLICATION
- The holistic checks all passed
- The average precision is above 90%

### 2. Trace a Finding

For any finding in the review, you can trace it back through the pipeline:

1. **Find the finding** in `output/review_EN.md`
2. **Identify the originating agent** by matching the finding's topic to the agent dimension (e.g., an equation error came from math-logic)
3. **Read the agent output** in `agent_outputs/[agent].md` to see the original finding with full evidence and reasoning
4. **Check the chunk** that produced it by looking up the location (section + page) in `chunks/chunk_map.json`
5. **Verify against the paper** by reading the corresponding passage in `input/[name]_converted.md`

### 3. Check Reference Verification

For reference-related findings:

1. Read `verification/reference_report.json` for the full per-reference verification results
2. Each entry shows which API was used, the similarity score, and any suspicion reasons
3. Cross-reference with `agent_outputs/references.md` for the agent's interpretation

### 4. Check Confidence Iteration

For findings that went through confidence iteration:

1. Read `agent_outputs/confidence_check.md`
2. Each reviewed finding shows: original confidence, action taken (confirm/revise/withdraw), new confidence, and reasoning

### 5. Check Precision Validation

For the final validation status of each finding:

1. Read `verification/validation_report.json`
2. Each entry shows: tier (A or B), precision score, status (accepted/flagged/downgraded), number of iterations, and notes

---

## How to Reproduce a Review

To reproduce a review:

1. Use the same PDF file (verify with a checksum: `sha256sum paper.pdf`)
2. Run `/review path/to/paper.pdf` from the same version of the refine-ink repository
3. Compare the output

Note that exact reproduction is not guaranteed because:

- LLM outputs are non-deterministic (temperature > 0)
- Web search results change over time
- API databases are updated regularly (references that were unverifiable may become verified, and vice versa)
- Google Scholar results depend on session state and geographic location

However, the overall structure, severity distribution, and major findings should be substantially similar across runs.

---

## Compliance

The audit trail provides evidence for:

| Requirement | Evidence |
|---|---|
| **The review was based on the actual paper** | Conversion verification report shows content fidelity; spot checks confirm sentences from the PDF appear in the Markdown |
| **Every finding is traceable to specific text** | Agent outputs include verbatim quotes with section + page locations; the precision validator re-checked every quote |
| **No findings were hallucinated** | Anti-hallucination rules enforced across all agents; external knowledge is explicitly marked; confidence iteration and precision validation filter false positives |
| **References were independently verified** | Reference verification report shows which APIs confirmed each reference; unverifiable and suspicious references are explicitly flagged |
| **The recommendation matches the findings** | Precision validation holistic check includes recommendation calibration |
| **The review was generated systematically** | The full agent execution trace is logged: which agents ran, how many chunks they processed, how many findings they produced, and how long they took |
