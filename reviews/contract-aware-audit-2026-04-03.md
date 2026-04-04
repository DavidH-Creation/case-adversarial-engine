# Contract-Aware Audit

Date: 2026-04-03

## Track 1: Audit Memo

The earlier product review was directionally right as a product critique, but overstated as a `main`-branch repo audit.

The more accurate repo-aware reading is:

1. The mainline problem was not "missing ontology."  
   The canonical issue ontology already existed, but it was not being enforced cleanly at the render boundary or in regression gates.

2. The mainline problem was not "public output still shows probability and mediation."  
   The public contract had already moved away from those semantics, but the internal acceptance gate still depended on legacy path logic.

3. The repo was not purely single-case anymore.  
   Multi-case fixtures and harnesses existed, but behavior-level generalization acceptance was still weak.

4. The highest-priority defect was contract divergence.  
   Public output semantics, sample outputs, and acceptance logic were not all protecting the same contract.

## Track 2: Remediation Backlog

### P0 Completed

- Rewrote `scripts/run_acceptance.py` so mainline pass conditions match the current output contract.
- Removed `mediation_path` as a required mainline acceptance condition.
- Replaced single-issue frequency with ordered issue-tree stability.
- Replaced legacy path explainability with current artifact-based explainability.
- Added a render-contract linter for user-visible Markdown.
- Wired `write_v3_report_md()` to fail before writing polluted or unfinished output.
- Replaced the checked-in `outputs/v3/report.md` with a render-clean baseline.

### P1 Still Open

- Separate harness validation from behavior validation more explicitly in docs and CI reporting.
- Add behavior-level acceptance runs for at least one `civil_loan`, one `labor_dispute`, and one `real_estate` case using real model runs or stable recorded artifacts.
- Record per-case metrics for issue-tree stability, citation completeness, render cleanliness, and section completeness.
- Extend parity checks from Markdown into extracted DOCX text in the same render gate.

## Thesis

The repo's main weakness was not lack of abstraction. It was failure to turn existing abstractions into enforced product contracts.
