# Evidence Indexer Contract

**Engine:** `case_structuring`  
**Component:** `evidence_indexer`  
**Version:** v0.5  
**Schema:** `schemas/case/evidence_index.schema.json`

---

## Purpose

The evidence indexer transforms a list of raw case material segments into structured `Evidence` objects and registers them into `CaseWorkspace.material_index.Evidence`. It is the canonical entry point for all case materials in the `case_structuring` stage.

---

## I/O Contract

### Input

```
Array<RawMaterial>
```

Each `RawMaterial` has:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | `string` | Yes | Stable identifier for the material segment. Must be unique within the input batch. |
| `text` | `string` | Yes | Plain text content. v0.5: no OCR; caller provides text directly. |
| `metadata` | `object` | Yes | Open metadata bag (document_type, date, submitter, etc.). |

**v0.5 constraint:** Input is a simple `{ source_id, text, metadata }` array. No OCR pipeline, no binary attachments.

### Output

```
Array<Evidence>
```

Each `Evidence` conforms to `schemas/case/evidence.schema.json`.

Guaranteed post-indexing invariants:

| Field | Guaranteed Value |
|-------|-----------------|
| `status` | `"private"` |
| `access_domain` | `"owner_private"` |
| `target_fact_ids` | non-empty array (≥ 1 entry) |
| `submitted_by_party_id` | `null` |
| `challenged_by_party_ids` | `[]` |
| `evidence_id` | globally unique |

**Canonical write path:** `CaseWorkspace.material_index.Evidence`

---

## Execution Model

The indexer runs as a **Job + Run** pair:

```
Job (job_type = "evidence_indexing")
  └─ Run
       ├─ input_snapshot.material_refs  → (empty at intake; raw_materials passed directly)
       ├─ output_refs                   → [ artifact_ref → EvidenceIndexArtifact ]
       └─ EvidenceIndexArtifact
            ├─ raw_materials            (input replay snapshot)
            └─ evidences               (output Evidence array)
```

- `Job.result_ref` → `artifact_index` entry pointing at the `EvidenceIndexArtifact`
- `Run.output_refs` → same `artifact_ref`
- After completion: each `Evidence` in `evidences` is registered as a `material_index.Evidence` entry

**Job lifecycle:**

| State | `progress` | Notes |
|-------|-----------|-------|
| `created` | `0` | Job record created, not yet dispatched |
| `running` | `(0, 1)` | Indexing in progress |
| `completed` | `1` | All Evidence written; `result_ref` populated |
| `failed` | `(0, 1)` | `error` populated; no partial writes committed |

---

## Constraints

1. **Source uniqueness:** Each `source_id` in the input batch must be unique. Duplicate `source_id` is a hard error.
2. **Fact binding:** Every output `Evidence` must bind at least one `target_fact_id`. Evidence without a fact proposition is rejected.
3. **Evidence ID uniqueness:** `evidence_id` values must be globally unique within the workspace. Collision is a hard error.
4. **No status promotion:** The indexer sets `status = "private"` unconditionally. Promotion to `submitted` or beyond is the responsibility of the procedure engine.
5. **No access escalation:** The indexer sets `access_domain = "owner_private"` unconditionally. Domain changes require explicit procedure transitions.
6. **Atomic batch:** All Evidence objects from a batch are committed together. Partial writes are not allowed; a failed item fails the entire job.
7. **No OCR (v0.5):** Text content must be provided by the caller. Binary or image-only materials are out of scope.

---

## Acceptance Criteria

A completed evidence indexer run passes acceptance when:

1. **Schema validation:** Every `Evidence` in `evidences` validates against `schemas/case/evidence.schema.json` with zero errors.
2. **Fact binding:** Every `Evidence` has `target_fact_ids.length >= 1`.
3. **Initial state:** Every `Evidence` has `status = "private"` and `access_domain = "owner_private"`.
4. **ID uniqueness:** All `evidence_id` values are distinct within the artifact.
5. **Source coverage:** Every input `source_id` maps to at least one output `Evidence`.
6. **Gold fixture comparison:** Output matches `benchmarks/fixtures/evidence_indexer_output.json` on the required fields: `evidence_id`, `target_fact_ids`, `target_issue_ids`, `access_domain`, `status`.

---

## Out of Scope (v0.5)

- OCR / binary document parsing
- Automated issue binding (`target_issue_ids` may be populated by caller or left empty)
- Deduplication across batches
- Evidence challenge or admission workflow
- Multi-party submission routing
