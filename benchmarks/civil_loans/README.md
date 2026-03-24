# Civil Loans Benchmark (民间借贷)

## Directory Layout

```
benchmarks/civil_loans/
  README.md                   ← this file
  case_manifest.schema.json   ← JSON Schema for a single benchmark case manifest
  template/                   ← fully worked template case (civil-loan-tpl-001)
    case_manifest.json
    source_materials/
      README.md               ← describes required input documents
    gold_issue_tree.json      ← gold-standard Issue objects
    gold_evidence_index.json  ← gold-standard Evidence objects
    gold_burden_map.json      ← gold-standard Burden objects
    lawyer_notes.json         ← fact / inference / experience_advice notes
  {case_id}/                  ← one directory per real benchmark case
    case_manifest.json
    source_materials/
    gold_issue_tree.json
    gold_evidence_index.json
    gold_burden_map.json
    lawyer_notes.json
```

## ID Naming Convention

All object IDs follow `{type}-{case_slug}-{seq}`, e.g.:

| Object   | Example ID                         |
|----------|------------------------------------|
| Party    | `party-civil-loan-tpl-001`         |
| Evidence | `evidence-civil-loan-tpl-001`      |
| Issue    | `issue-civil-loan-tpl-001`         |
| Burden   | `burden-civil-loan-tpl-001`        |

## Adding a New Case

1. Copy `template/` to `benchmarks/civil_loans/{case_id}/`.
2. Fill in all gold files using real case materials.
3. Register the case in a future `civil_loans_index.json` (created when ≥5 cases exist).
4. Validate all gold fixtures against `case_manifest.schema.json`.

## v0.5 Dataset Target

- At least **20** annotated civil-loan cases required before v0.5 acceptance.
- Each case must fully populate: issue tree, evidence index, burden map, lawyer notes.
- See `benchmarks/acceptance/v0_5_pass_criteria.json` for machine-readable thresholds.

## Field Alignment

All gold objects conform to the canonical object model in `docs/03_case_object_model.md`.
Object types used: `Party`, `Issue`, `Evidence`, `Burden`.
Lawyer notes use `statement_class` values: `fact`, `inference`, `experience_advice`.
