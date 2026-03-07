# Statistical Pitfalls, Cognitive Biases, and Logical Fallacies Reference

This reference list is for ALL review agents. When reviewing, be alert to these common issues. Do NOT use this list as a checklist to report against — only flag items you actually detect in the paper with evidence.

---

## Statistical Pitfalls

These are common methodological errors in social science research. Flag them when detected with evidence from the paper.

### Inference Errors
1. **Misinterpreting p-values**: Treating p < 0.05 as "true" and p > 0.05 as "no effect" rather than evaluating effect sizes and confidence intervals
2. **Comparing significance across groups**: Saying "X is significant but Y is not, so X differs from Y" without a formal interaction/difference test
3. **Treating non-significance as evidence of no effect**: Failure to consider statistical power; absence of evidence ≠ evidence of absence
4. **Multiple comparisons without correction**: Testing many hypotheses without adjusting for false discovery rate (Bonferroni, Benjamini-Hochberg, Romano-Wolf)
5. **p-hacking / specification searching**: Selectively reporting favorable specifications from among many tested
6. **HARKing (Hypothesizing After Results are Known)**: Presenting exploratory findings as if they were hypothesized a priori
7. **Winner's curse**: Reporting the largest effect from many specifications; true effect is likely smaller
8. **Inflated effect sizes from small samples**: Small samples produce noisier estimates that, when significant, tend to overestimate effects

### Design Errors
9. **Bad controls (post-treatment variables)**: Controlling for variables that are themselves affected by the treatment, inducing collider bias
10. **Endogenous sample selection**: Conditioning on an outcome that is affected by the treatment (e.g., wages conditional on employment)
11. **Ecological fallacy**: Interpreting group-level associations as individual-level effects
12. **Simpson's paradox**: Aggregation reversing the direction of an association
13. **Survivorship bias**: Analyzing only units that "survived" a selection process related to treatment
14. **Collider bias (Berkson's paradox)**: Conditioning on a common effect of two variables creates a spurious association
15. **Regression to the mean**: Interpreting natural mean-reversion as a treatment effect
16. **Reverse causality**: The outcome may cause the "treatment" rather than vice versa

### Estimation Errors
17. **Omitted variable bias**: Leaving out a confounding variable that correlates with both treatment and outcome
18. **Measurement error in the dependent variable**: Adds noise but does not bias OLS (classical errors)
19. **Measurement error in the independent variable**: Attenuates OLS coefficients toward zero (classical errors-in-variables)
20. **Functional form misspecification**: Using linear models for nonlinear relationships, or vice versa
21. **Multicollinearity**: High correlation among regressors inflating standard errors (not bias, but imprecision)
22. **Heteroskedasticity ignored**: Using standard OLS standard errors when errors are heteroskedastic
23. **Clustered data with individual-level standard errors**: Understating standard errors when observations are grouped

### Data Quality and Measurement Errors
24. **Definitional inconsistency across sources**: Combining data from multiple databases (e.g., WHO, Eurostat, OECD) without verifying that variables use the same definition (headcount vs full-time equivalents; practising vs professionally active vs licensed)
25. **Non-overlapping observation windows**: Computing and comparing statistics across units when the available years differ substantially, making magnitudes non-comparable
26. **Series breaks and reclassifications**: Changes in data collection methodology creating artificial jumps or trends that contaminate time-series analysis
27. **Universal qualifier overclaiming**: Using "uniformly," "always," "in every country," "without exception" when the data contain missing values, non-significant estimates, or exceptions

### Systematic Review Pitfalls
28. **Missing construct definition**: Failing to operationally define the central construct (e.g., "digital trade rules," "fintech adoption") before applying inclusion criteria, leaving the unit of analysis ambiguous across research questions
29. **Overly narrow search string**: Hardwiring mandatory AND terms (e.g., "development" AND "effect") that mechanically exclude literature relevant to some research questions (e.g., studies addressing evolution or structure but not effects)
30. **Cross-database field inconsistency**: Searching "anywhere in article" in Google Scholar while restricting to TITLE-ABS-KEY in Scopus/Web of Science, producing non-comparable retrieval across databases
31. **Method taxonomy errors**: Conflating estimation techniques (PPML, OLS, MLE) with model specifications (gravity, structural) or identification designs (DID, RDD, IV) when classifying the reviewed literature's methods
32. **Missing data extraction protocol**: No documented extraction form, coding rulebook, or borderline-case handling procedure, making the qualitative categorisation unauditable
33. **Conflating visualisation type with analytical claim**: Interpreting a bibliometric keyword co-occurrence map (VOSviewer) as evidence of geopolitical network structure, or treating a citation network as evidence of intellectual influence

### Interpretation Errors
34. **Confusing correlation with causation**: Drawing causal conclusions from associational evidence
35. **Confusing statistical significance with economic significance**: A tiny but precisely estimated effect may be statistically significant but economically meaningless
36. **Over-generalizing from LATE**: Interpreting a local average treatment effect as a general average treatment effect
37. **Extrapolation beyond support**: Drawing conclusions for populations or settings not represented in the data
38. **Ignoring external validity**: Findings from a specific context may not generalize

---

## Cognitive Biases in Research

Be alert to these biases in the paper's reasoning and your own evaluation:

1. **Confirmation bias**: Seeking evidence that supports a hypothesis while ignoring contradictory evidence
2. **Anchoring bias**: Over-relying on the first piece of information encountered (e.g., design looks acceptable because results look good)
3. **Publication bias / file drawer problem**: Positive results are more likely to be published, skewing the evidence base
4. **Status quo bias**: Accepting conventional methods without questioning their appropriateness for the specific context
5. **Overconfidence bias**: Authors being too certain about their results without acknowledging uncertainty
6. **Framing effects**: The same result presented differently (e.g., "90% survival" vs "10% mortality") leads to different interpretations
7. **Availability bias**: Overweighting memorable or recent evidence over systematic evidence
8. **Narrative fallacy**: Constructing a compelling story that fits the results without testing the story against alternatives
9. **Texas sharpshooter fallacy**: Finding patterns in data post hoc and presenting them as if predicted a priori
10. **Base rate neglect**: Ignoring how common the outcome is in the population when interpreting test results

---

## Logical Fallacies in Academic Arguments

Flag these when they appear in the paper's argumentation:

1. **Affirming the consequent**: "If A then B; B is true; therefore A is true" — other explanations for B exist
2. **False dichotomy**: Presenting only two options when more exist
3. **Hasty generalization**: Drawing broad conclusions from limited evidence
4. **Appeal to authority**: Citing a prominent paper as if the conclusion is beyond question, without evaluating the evidence
5. **Straw man**: Misrepresenting an alternative theory to make it easier to dismiss
6. **Post hoc ergo propter hoc**: Assuming causation from temporal sequence
7. **Circular reasoning**: The conclusion is implicitly assumed in the premises
8. **Equivocation**: Using a term with different meanings in different parts of the argument
9. **False equivalence**: Treating two things as comparable when they differ in important ways
10. **Composition/Division fallacy**: Assuming what is true of parts is true of the whole, or vice versa
11. **No true Scotsman**: Redefining terms to exclude counterexamples
12. **Begging the question**: Assuming the conclusion in the premise

---

## Usage Guidelines

- **DO NOT** mechanically apply this list. These are awareness prompts, not a checklist.
- **ONLY flag** items you find genuine evidence for in the paper itself.
- **Quote exact text** when flagging any of these issues.
- **Assign appropriate severity**: A logical fallacy in a footnote is minor; a logical fallacy in the core identification argument is critical.
- **Be fair**: Many of these issues involve judgment calls. If the paper handles an issue imperfectly but acknowledges the limitation, reduce severity.
