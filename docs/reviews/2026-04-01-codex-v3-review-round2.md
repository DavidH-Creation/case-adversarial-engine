# V3 4-Layer Report — Codex Adversarial Review Round 2

**Date**: 2026-04-01
**Reviewer**: Claude Opus (post-fix verification)
**Scope**: engines/report_generation/v3/

## Summary

All critical findings from the Round 1 Codex adversarial review have been addressed.
47/47 tests pass. Ruff lint clean.

## Findings Fixed

### A. Neutral/Perspective Separation (CRITICAL — FIXED)

| File | Issue | Fix |
|------|-------|-----|
| `layer2_core.py` | Fed `adversarial_result` and `attack_chain` directly; Layer 2 built scenario tree internally | Removed `decision_tree` param; accepts pre-built `scenario_tree` from caller. `adversarial_result` now used ONLY for dispute detection (fact_base) and neutral both-sides presentation (issue_map). |
| `layer1_cover.py` | `overall_assessment` labeled as 「事実」 | Changed to `SectionTag.inference` — overall assessments are inferences, not facts. |
| `issue_map.py` | Plaintiff/defendant theses embedded without source attribution | Added `[来源:对抗分析]` prefix to theses sourced from adversarial arguments. |

### B. Logic Bugs (FIXED)

| File | Issue | Fix |
|------|-------|-----|
| `fact_base.py` | Unchallenged evidence treated as undisputed fact | Now requires BOTH: (1) third-party verifiable source (bank/notary/court) AND documentary/physical type, OR (2) evidence referenced by BOTH parties. Absence of challenge alone is insufficient. |
| `evidence_classifier.py` | Challenged evidence with `admissibility_score >= 0.5` could stay green | Added early return: any challenged evidence is **yellow at best**, regardless of type or source. Red for `score < 0.5`, yellow for `score >= 0.5`. Removed dead code at function end. |
| `scenario_tree.py` | Produced flat linked list (all paths chained via `no_child_id`) | Implemented recursive binary partitioning: middle path becomes root, left paths → yes-subtree, right paths → no-subtree. Produces actual branching tree. |
| `report_writer.py` | Scenario tree built twice (L63 and inside `build_layer2`) | Built ONCE in `build_four_layer_report`, passed to both `build_layer1` and `build_layer2` as pre-built parameter. |

### C. Type Safety (FIXED)

| File | Issue | Fix |
|------|-------|-----|
| `models.py` | `PerspectiveOutput.perspective` and `FourLayerReport.perspective` were `str` | Changed to `Literal["plaintiff", "defendant", "neutral"]`. Invalid values now rejected at validation time. |
| `tag_system.py` | `_STATEMENT_CLASS_TO_TAG` missing `opinion` and `recommendation` | Added both mappings. `statement_class_to_tag("opinion")` → `SectionTag.opinion`, `statement_class_to_tag("recommendation")` → `SectionTag.recommendation`. |

### D. Unused Parameters (FIXED)

| File | Issue | Fix |
|------|-------|-----|
| `layer3_perspective.py` | `build_layer3()` accepted `issue_tree`, `evidence_index`, `exec_summary` but never used them | Now passed to `_build_plaintiff_output` and `_build_defendant_output`. Used for: evidence supplement fallback (weak evidence identification), challenge target fallback, over-assertion warning enrichment (issue titles), exec_summary immediate actions. |

## Test Coverage

- **47 tests pass** (was 40 before, added 7 new tests)
- New tests:
  - `test_challenged_high_admissibility_is_yellow_not_green` — verifies challenged bank records can't be green
  - `test_challenged_medium_admissibility_is_yellow` — verifies challenged notary docs can't be green
  - `test_tree_is_not_flat_linked_list` — verifies binary branching with 3+ paths
  - `test_neutral_conclusion_tagged_as_inference` — verifies 「推断」 tag on conclusion
  - `test_invalid_perspective_rejected` — verifies Literal type enforcement on PerspectiveOutput
  - `test_report_invalid_perspective_rejected` — verifies Literal type enforcement on FourLayerReport
  - `test_statement_class_to_tag` extended — verifies opinion and recommendation mappings

## Files Changed (10)

1. `engines/report_generation/v3/models.py` — Literal type for perspective
2. `engines/report_generation/v3/tag_system.py` — opinion/recommendation mappings
3. `engines/report_generation/v3/evidence_classifier.py` — challenged evidence cap
4. `engines/report_generation/v3/fact_base.py` — undisputed fact criteria
5. `engines/report_generation/v3/layer1_cover.py` — inference tag on conclusion
6. `engines/report_generation/v3/layer2_core.py` — pre-built scenario tree, neutrality docs
7. `engines/report_generation/v3/issue_map.py` — source attribution
8. `engines/report_generation/v3/scenario_tree.py` — binary tree branching
9. `engines/report_generation/v3/report_writer.py` — single tree build
10. `engines/report_generation/v3/layer3_perspective.py` — grounded with issue_tree/evidence_index/exec_summary
