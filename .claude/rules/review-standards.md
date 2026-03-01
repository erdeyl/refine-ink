# Review Quality Standards

These standards apply to all review agents. All findings must conform to the severity classification, verbatim correction requirements, and output format specified below. Standards are calibrated to the expectations of top economics journals (AER, QJE, Econometrica, JFE).

---

## Severity Levels

Every finding must be classified into exactly one severity level. Calibrate your assessment as a referee would at a top-5 economics journal.

### Critical
Errors that invalidate results, fundamental logical flaws, or incorrect proofs.

Examples:
- An identification assumption is violated by the paper's own data or design
- A proof contains a step that does not follow, rendering the theorem unproven
- A key regression coefficient is computed incorrectly and the main result depends on it
- The sign of a central result is wrong
- A fundamental misapplication of an econometric method (e.g., using OLS when the estimator requires IV, and this changes the conclusion)

### Major
Methodological concerns that could change conclusions, or significant gaps in the literature.

Examples:
- A robustness check that is standard for this type of analysis is missing and could plausibly overturn results
- The paper omits a highly relevant competing explanation that is well-known in the literature
- Standard errors are clustered at the wrong level, and correcting this would likely change significance
- A key variable is measured with error and no correction is attempted
- Sample selection issues that are acknowledged but not addressed

### Minor
Notation inconsistencies, unclear exposition, or missing details that do not affect results.

Examples:
- A variable is defined as $X$ in Section 2 but appears as $x$ in Section 4
- A table note says "robust standard errors" but the methodology section says "clustered"
- An acronym is used before being defined
- A figure axis label is missing or misleading
- A paragraph is hard to follow but the underlying logic is sound

### Suggestion
Optional improvements, alternative approaches, or additional robustness checks.

Examples:
- An additional heterogeneity analysis that would strengthen the paper
- A more recent reference that supports or qualifies a claim
- An alternative functional form that could be explored
- A visualization that would help readers understand a complex result
- Stylistic improvements that would improve readability

---

## Verbatim Correction Requirement

Every error finding (Critical, Major, or Minor) MUST include a specific, actionable correction. The correction must be concrete enough that the author can implement it directly.

### Text Corrections
- **Quote the incorrect passage** using `> quote` format
- **Provide the corrected text**, up to a full rewritten paragraph if necessary
- The corrected text must preserve the author's voice and intent while fixing the error

Example:
```
> "The coefficient on income is 0.45 (p < 0.01), indicating a strong negative relationship."

Correction: "The coefficient on income is 0.45 (p < 0.01), indicating a strong positive relationship."
Reasoning: A positive coefficient (0.45) indicates a positive relationship, not a negative one.
```

### Table Corrections
- **Identify the specific cell** by row and column labels
- **Provide the corrected value** with reasoning

Example:
```
Table 3, Row "Female", Column "Model (2)": reported value is 0.234, but based on
the coefficient in Model (1) (0.312) and the stated adjustment factor (0.75),
the correct value should be 0.234. [Or: the correct value should be 0.312 × 0.75 = 0.234,
which matches — but the text on p. 15 reports this as 0.243, which is a transposition error.]
```

### Numerical Corrections
- **Quote the context** where the number appears
- **Provide the correct value** with a derivation showing how it was computed

### Equation Corrections
- **Show the incorrect equation** as written in the paper
- **Show the corrected equation** with a step-by-step explanation of what changed and why

Example:
```
Incorrect (Eq. 7, p. 12):
  $\hat{\beta} = (X'X)^{-1}X'Y$

Corrected:
  $\hat{\beta} = (X'X)^{-1}X'y$

Explanation: The dependent variable should be lowercase $y$ (the vector of observations),
consistent with the notation established in Eq. 3 where $Y$ denotes the matrix of
endogenous variables in the system.
```

### Econometric Method Corrections
- **Recommend a specific alternative** method
- **Provide justification** for why the alternative is more appropriate
- **Include at least one reference** to a methodological paper (if known from the document's own references; otherwise mark as EXTERNAL KNOWLEDGE)

### Notation Corrections
- **Show the inconsistency** with exact locations of each variant
- **Recommend a standardized form** and specify which convention to adopt throughout

---

## Writing Quality Standards

All corrections and commentary must meet the following quality bar:

1. **Scientifically exact**: Every statement must be precise and technically correct.
2. **Human-like prose**: Write as a senior colleague at a top journal would — direct, constructive, collegial. Avoid robotic or template-like phrasing.
3. **Self-contained**: Each finding must be understandable on its own, without requiring the reader to look up other findings.
4. **Contextualized**: Explain WHY the issue matters, not just WHAT the issue is. A finding that says "this number is wrong" without explaining the consequence is incomplete.

### Hungarian-Language Papers

For papers written in Hungarian:
- All corrections to the paper's text must use proper Hungarian academic register (tudományos regiszter)
- Technical terminology must follow established Hungarian conventions in the relevant field
- Commentary and meta-discussion (severity assessment, reasoning) may be in English

---

## Finding Output Format

Every finding must include ALL of the following fields:

| Field | Description |
|-------|-------------|
| `finding_text` | Clear, concise description of the issue |
| `severity` | One of: `critical`, `major`, `minor`, `suggestion` |
| `confidence` | Integer 0–100 indicating certainty that this is a genuine issue |
| `evidence` | Exact quote from the document demonstrating the issue (block-quote format) |
| `location` | Section name + page number (e.g., "Section 3.2, p. 14") |
| `correction` | Verbatim recommendation: the specific text, value, equation, or method to replace the error |

Findings missing any of these fields are incomplete and must not be submitted.
