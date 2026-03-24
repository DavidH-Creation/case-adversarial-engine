# Scenario Engine Contract

**Workflow stage:** `simulation_run`  
**Schema:** `schemas/case/scenario.schema.json`

---

## Overview

The Scenario Engine executes a counterfactual variation on a completed baseline Run. It applies a structured `change_set` (variable injection list) to the baseline's input snapshot, re-runs the simulation, and produces:

1. A new **Run** object with a non-null `scenario_id` registered under `CaseWorkspace.run_ids`.
2. A populated **`diff_summary`** on the Scenario object explaining per-issue impact relative to the baseline.

The engine does **not** generate speculative strategies or suggest what changes to make — it only executes a caller-supplied `change_set` and reports the outcome.

---

## Input Contract

| Field | Type | Required | Description |
|---|---|---|---|
| `scenario_id` | `string` | yes | Pre-allocated ID for the Scenario being executed |
| `baseline_run_id` | `string` | yes | `run_id` of the completed Run used as baseline |
| `change_set` | `ChangeItem[]` | yes | Ordered list of field mutations to apply before re-execution (may be empty for baseline anchor) |
| `workspace_id` | `string` | yes | CaseWorkspace owning this execution |

### ChangeItem structure

```json
{
  "target_object_type": "Evidence",
  "target_object_id": "evidence-promissory-note-001",
  "field_path": "body",
  "old_value": "借条原件，金额 ¥50,000",
  "new_value": "借条复印件，金额 ¥50,000，原件遗失"
}
```

- `target_object_type`: must be a type registered in `CaseWorkspace.material_index` or `artifact_index`.
- `field_path`: dot-notation path into the target object (e.g. `"amount"`, `"evidence_citations.0"`).
- `old_value` / `new_value`: any JSON-serializable value; `null` is permitted.
- Change items are applied in array order; later items may reference fields already mutated by earlier items.

### Preconditions

1. The baseline Run must have `status = "completed"`.
2. Every `target_object_id` in `change_set` must resolve in the workspace's `material_index` or `artifact_index`.
3. `change_set` must structurally record each change item (no implicit or out-of-band mutations).

---

## Output Contract

### New Run object

The engine registers a new Run with:

| Field | Value |
|---|---|
| `scenario_id` | the executing scenario's `scenario_id` (non-null) |
| `trigger_type` | `"scenario_execution"` |
| `input_snapshot` | baseline Run's `input_snapshot` with change_set mutations applied |
| `status` | `"completed"` on success, `"failed"` on error |

The new `run_id` is appended to `CaseWorkspace.run_ids`.

### Updated Scenario object

After execution, the engine writes back to the Scenario:

| Field | Value |
|---|---|
| `diff_summary` | Populated `DiffEntry[]` (one per affected issue) |
| `affected_issue_ids` | Issue IDs whose analysis changed |
| `affected_evidence_ids` | Evidence IDs referenced or mutated by `change_set` |
| `status` | `"completed"` on success, `"failed"` on error |

### DiffEntry structure

```json
{
  "issue_id": "issue-default-001",
  "impact_description": "Evidence downgraded from original to copy; credibility of repayment obligation weakened.",
  "direction": "weaken"
}
```

- `direction` is one of `"strengthen"` | `"weaken"` | `"neutral"`.
- Every `diff_entry` must be traceable to at least one `change_item` in the `change_set`.
- Issues not affected by the change_set are omitted from `diff_summary`.

### Postconditions

1. The new Run's `scenario_id` is non-null and matches the Scenario's `scenario_id`.
2. The new Run's `run_id` appears in `CaseWorkspace.run_ids`.
3. `diff_summary` is a `DiffEntry[]` (not the sentinel string `"baseline"`).
4. Every `diff_entry.issue_id` appears in `affected_issue_ids`.
5. `CaseWorkspace.active_scenario_id` is updated to the executing `scenario_id` on success.

---

## Constraints

| Constraint | Rule |
|---|---|
| Structural completeness | Every mutation must appear as a `ChangeItem` in `change_set`. No implicit side-channel changes. |
| Explainability | Every `diff_entry.impact_description` must be a non-empty, human-readable string traceable to the change_set. |
| Baseline anchor | A Scenario with `change_set = []` and `diff_summary = "baseline"` is the canonical baseline. The engine must not re-execute a baseline scenario. |
| No strategy generation | The engine reports outcomes only. It does not suggest further changes or generate follow-on scenarios. |
| Run immutability | The baseline Run is never mutated. The engine creates a new Run for each scenario execution. |
| Workspace registration | The new Run's `run_id` must be appended to `CaseWorkspace.run_ids` before the engine reports completion. |

---

## Error Handling

If any precondition fails or execution errors, the engine must:

1. Set `Scenario.status = "failed"` and leave `diff_summary` as the pre-execution value.
2. Set the new Run's `status = "failed"` (if a Run was created before the error).
3. Not append the failed Run's `run_id` to `CaseWorkspace.run_ids`.

---

## Baseline vs. Scenario Scenario lifecycle

```
Scenario (baseline anchor)          Scenario (counterfactual)
  change_set: []                      change_set: [ChangeItem, ...]
  diff_summary: "baseline"            diff_summary: DiffEntry[]
  status: "completed"                 status: "completed"
       |                                    |
       v                                    v
  Run (baseline)                      Run (scenario output)
  scenario_id: <id>                   scenario_id: <same id>
  trigger_type: *                     trigger_type: "scenario_execution"
```
