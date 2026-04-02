> Historical document.
> Archived during the April 2026 documentation reorganization.
> Kept for context only. Do not treat this file as the current source of truth.
---
date: 2026-04-01
topic: v3-output-improvements
type: delta-plan
status: completed
revision: 3 (v3.2 baseline + export parity cleanup)
baseline: v3.2 on main via commit 612f960 (2026-04-02)
---

# V3.2 Output Delta

## Summary

This file is no longer an implementation plan for building V3. The V3.2 report
stack is already on `main`. This document records the shipped baseline, the
product decisions locked for the cleanup delta, and the concrete parity work
completed to finish the migration.

Two product decisions are now explicit:

- Mainline output does not render mediation / settlement-range content.
- User-facing output is probability-free. No percentages, no qualitative
  probability labels, no `prob=` summaries, and no confidence-interval wording
  in report surfaces.

## Current Baseline

As of April 2, 2026, `main` already shipped the core V3.2 architecture:

- Four-layer markdown report generation
- Conditional scenario tree output
- Perspective-aware output via `--perspective`
- DOCX export as a first-class surface
- Resume/checkpoint support in `scripts/run_case.py`

That means the remaining work was not "build V3", but "finish the semantic
migration and make the exports agree."

## Why This Delta Existed

The repo had already removed pseudo-probability from parts of the pipeline, but
several active consumers still leaked the old semantics:

- DOCX still rendered path probability labels or probability-driven ordering
- Legacy markdown helpers still accepted mediation output
- Shared helpers still emitted probability/confidence wording
- Resume-based CLI generation lacked a stable parity smoke for markdown + DOCX

That created a mixed user story: one surface said "no fake probability", while
another quietly kept saying it.

## Completed Delta

### 1. Reframed this document

This file now treats `main` as the baseline and records the delta only. The old
"feature phases" were removed because they described work that was already
landed in the repository.

### 2. Removed mediation from mainline output surfaces

Mainline report generation no longer renders mediation content.

Completed behavior:

- DOCX mainline rendering no longer includes mediation sections
- Legacy markdown helpers no longer emit mediation sections in active output
- `scripts/run_case.py --with-mediation` remains accepted for compatibility, but
  is now a deprecated no-op

Non-goal:

- The legacy `mediation_range.py` helper may remain in the tree as dormant /
  internal code as long as active report surfaces do not call it

### 3. Finished the probability-free output migration

User-facing output now uses path order and trigger conditions, not probability
display.

Completed behavior:

- DOCX path rendering uses `DecisionPathTree.path_ranking` order when present;
  otherwise it preserves source path order
- DOCX no longer shows percentages, qualitative probability labels, or
  probability rationale text
- `engines/shared/display_resolver.py` no longer appends probability suffixes
- executive summary helpers no longer expose probability/confidence wording in
  user-facing summary text
- consistency-check output no longer includes `prob=` style messages
- outcome-path helpers no longer derive risk points from
  `probability_rationale`

Compatibility rule:

- Probability / confidence fields remain in pipeline models for backward
  compatibility with existing serialized artifacts
- New output code does not treat those fields as authoritative

### 4. Added real resume-based export parity coverage

The CLI resume path now hydrates post-debate artifacts from disk before Step 4
/ 5 output generation, so markdown and DOCX can be regenerated without rerunning
the LLM-heavy upstream pipeline.

Completed behavior:

- Resume after `step_3_5_post_debate` reloads:
  - `decision_tree`
  - `attack_chain`
  - `amount_report`
  - `exec_summary`
  - `action_rec`
  - `ranked_issues`
- The CLI now writes a stable `report.docx` alias even when the generator's
  human-facing filename remains localized
- A checked-in resume fixture covers markdown / DOCX regeneration from persisted
  artifacts

## Migration Matrix

| Surface | Old behavior | Final behavior |
|---|---|---|
| `docs/plans/2026-04-01-v3-improvements.md` | Pretended V3 core still needed to be built | Records shipped baseline + delta only |
| `engines/report_generation/docx_generator.py` | Probability labels and local probability ordering survived in output | Uses ranking/source order only; no probability wording |
| `scripts/run_case.py` markdown path | Mediation flag could still affect output | `--with-mediation` accepted but no longer changes mainline report output |
| `engines/shared/display_resolver.py` | Returned outcome plus probability suffix | Returns outcome text only |
| `engines/report_generation/executive_summarizer/*` | Exposed probability/confidence wording in summary text | Uses path/trigger language only |
| `engines/shared/consistency_checker.py` | Failure text surfaced `prob=` style wording | Failure text stays probability-free |
| `engines/report_generation/outcome_paths.py` | Derived risk points from `probability_rationale` | Leaves those risk points empty |
| CLI resume export path | Markdown/DOCX parity not directly guarded | Resume smoke covers regenerated markdown + DOCX |

## Public Interface Notes

No REST API contracts changed.

Intentional behavior changes:

- Repeated exposure of probability/confidence semantics in user-facing outputs
  is removed
- Mainline report output no longer includes mediation sections
- `--with-mediation` remains a compatibility flag but does not affect output
- `report.docx` is now a stable CLI output alias for downstream consumers

## Verification

Targeted verification completed:

- `pytest engines/report_generation/tests/test_docx_generator.py`
- `pytest engines/report_generation/tests/test_report_enhancements.py`
- `pytest engines/report_generation/executive_summarizer/tests/test_summarizer.py`
- `pytest engines/report_generation/tests/test_outcome_paths.py`
- `pytest engines/shared/tests/test_display_resolver.py`
- `pytest engines/shared/tests/test_consistency_checker.py`
- `pytest tests/smoke/test_run_case_resume_reports.py`

Coverage added / updated in this delta:

- DOCX no-probability assertions
- Markdown no-mediation assertions
- Shared helper probability-free assertions
- Resume-based markdown/DOCX parity smoke with checked-in fixture

## Out of Scope

This delta intentionally did not do the following:

- Delete deprecated probability/confidence fields from pipeline schemas
- Split large files such as `docx_generator.py`
- Refactor the broader report-generation architecture
- Change REST API schemas or add new CLI flags

Those are separate cleanup tasks. They are not required to make the shipped
V3.2 output semantics internally consistent.

