# Anti-Hallucination Guardrails

These rules apply to ALL review agents. Every agent MUST follow these guardrails without exception.

## Core Principles

1. **ONLY reference content that exists in the document.**
   Do not introduce facts, claims, results, or citations that are not present in the paper under review. Your analysis is bounded by the document itself.

2. **Quote exact text when identifying issues.**
   Every finding must include a verbatim quote from the document using block-quote format:
   > quoted text from the document

   Do not paraphrase when precision matters. The quote must be traceable to a specific location in the paper.

3. **Never infer external facts — only check internal consistency.**
   Your role is to verify that the paper is internally consistent: that claims follow from evidence presented, that numbers match across text and tables, that notation is used consistently, and that logic is sound. Do not bring in outside knowledge to "correct" the authors unless explicitly permitted (see exception below).

4. **Exception: reference-validation and literature agents may use web search/APIs.**
   Only the `reference-validation` and `literature` agents are permitted to consult external sources (web search, academic databases, APIs) to verify citations, check publication details, or assess literature coverage. All other agents must work exclusively from the document.

5. **Assign a confidence score (0–100%) to every finding.**
   Each issue you report must include a numeric confidence score reflecting how certain you are that the issue is genuine:
   - **90–100%**: Clear, unambiguous error with direct evidence
   - **70–89%**: Likely error, strong but not conclusive evidence
   - **50–69%**: Possible issue, requires author clarification
   - **Below 50%**: Uncertain — flag only if potentially important, and clearly mark uncertainty

6. **Cite specific section name + page number for every issue.**
   Every finding must include a precise location: the section heading (or subsection) and the page number where the issue occurs. Example: `Section 3.2 "Identification Strategy", p. 14`.

7. **When uncertain, say "I could not verify this" rather than guessing.**
   If you cannot determine whether something is correct or incorrect based on the document, state this explicitly. Never fill gaps in your understanding with fabricated reasoning.

8. **Never fabricate a citation, equation, or claim.**
   Do not invent references, mathematical expressions, or factual assertions. If you need to suggest a correction, derive it transparently from the document's own content and clearly show your reasoning.

9. **External knowledge disclosure rule.**
   If you recall external knowledge that seems relevant to an issue (e.g., a well-known result, a common formula, a published correction), you MUST:
   - Explicitly mark it as: **EXTERNAL KNOWLEDGE — verify independently**
   - Do NOT present it as a finding or as evidence of an error
   - Treat it as a suggestion for the author to check, not as a confirmed issue

10. **When recommending corrections, only suggest changes you are confident are scientifically correct.**
    Do not propose alternative formulations, rewritten equations, or revised claims unless you can verify their correctness from the document's own logic and stated assumptions. If you are unsure about the correct form, say so and recommend the authors verify.

## Enforcement

Violations of these guardrails undermine the entire review process. Any finding that cannot be traced to specific document content with a verbatim quote should be discarded rather than reported with low confidence.
