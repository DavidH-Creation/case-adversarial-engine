# Contract Alignment Update

Date: 2026-04-03

This note records the current enforced contract after the acceptance gate and render gate were aligned to the `main` branch output semantics.

## Current Mainline Contract

- Public output is `probability-free`.
- Public output is `mediation-free`.
- User-visible exports must not leak internal IDs or placeholder artifacts.

## Acceptance Contract

The acceptance runner now enforces the following semantics:

| Metric | Current meaning | Notes |
|---|---|---|
| `consistency` | Frequency of the most common ordered top-k issue sequence across successful runs | This is issue-tree stability, not single-issue frequency |
| `citation_rate` | Fraction of output slots with non-empty evidence citations | Unchanged |
| `path_explainable` | `decision_tree.json` exists, `report.md` exists, and at least one decision-tree branch has a real `trigger_condition` | No longer requires `mediation_path` |

## Render Contract

User-visible Markdown and DOCX exports now fail the render gate if they contain:

- internal tokens such as `issue-*`, `xexam-*`, `undefined`, or raw path IDs
- empty level-2 sections
- placeholder-only table rows such as `| - | - |`

## Scope Clarification

- Mock-LLM acceptance tests remain harness and structure checks.
- They do not prove behavior-level generalization.
- Cross-case behavior quality still requires real model runs or stable recorded artifacts across multiple case types.
