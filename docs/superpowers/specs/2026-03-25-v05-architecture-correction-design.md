# v0.5 Architecture Correction Design

## Status

Approved — ready for implementation planning.

## Context

Architecture review of case-adversarial-engine revealed five structural problems caused by skipping the brainstorming phase before implementation:

1. **S1**: Six engines each redefine shared types (IssueTree, EvidenceIndex, Burden, etc.) — no single source of truth
2. **S2**: CaseWorkspace has a full JSON Schema but zero engine integration — outputs are isolated artifacts
3. **S3**: evidence_indexer outputs Evidence, but issue_extractor needs Claims + Defenses + Evidence — data flow broken
4. **S4**: No orchestration layer to chain the six engines into a pipeline
5. **S5**: procedure_setup generates ProcedureSetupResult with no downstream consumer

## Decisions

| Issue | Decision | Rationale |
|-------|----------|-----------|
| S1 Shared models | Single `engines/shared/models.py` | v0.5 model count is manageable in one file; split later when it grows |
| S2 CaseWorkspace | Thin index `workspace.json` + independent artifact files | Aligns with schema's `storage_ref` design; atomic file writes prevent corruption |
| S3 Claim/Defense | New `claim_extractor` engine under `engines/case_structuring/` | Evidence extraction and claim extraction are distinct cognitive tasks; parallel execution |
| S4 Orchestration | Functional pipeline (`pipeline.py`) with CaseWorkspace checkpoints | Simpler than a state machine; checkpoint-based resume satisfies North Star's "unified workflow" requirement |
| S5 procedure_setup | Skip in v0.5 pipeline, preserve code, mark as v1 prep | ProcedureState constrains multi-role access; no multi-role interaction in v0.5 |

## 1. Shared Models — `engines/shared/models.py`

### Responsibility

Single definition point for all cross-engine Pydantic models and enums. Uses a **two-tier strategy** to reconcile docs/03 (authoritative names), JSON Schemas (contract surface), and engine code (working implementations).

### Two-tier strategy

- **Tier 1 (Stable fields)**: Fields that already exist in BOTH the JSON Schema AND the engine Pydantic code. These are required, typed, and enforced.
- **Tier 2 (Docs-forward fields)**: Fields defined in `docs/03_case_object_model.md` but NOT yet in the JSON Schema or engine code. These are added as `Optional` with defaults (`None` / `""`) so existing engine code and test fixtures compile without changes. JSON Schema alignment for these fields is deferred to a dedicated schema pass.

This means: **shared/models.py matches current engine code shape, plus docs/03 extras as Optional**. No engine code breaks on import.

### Compatibility table

| Type | Field | docs/03 | JSON Schema | Engine Code | shared/models.py |
|------|-------|---------|-------------|-------------|-------------------|
| **Issue** | description | required | ✗ absent | ✗ absent | Optional[str] = None (Tier 2) |
| **Issue** | priority | required | ✗ absent | ✗ absent | Optional[str] = None (Tier 2) |
| **Burden** | burden_party_id | required | N/A (B1 creates) | ✗ uses bearer_party_id | **burden_party_id** required (B2 renames) |
| **Burden** | burden_type | required | N/A (B1 creates) | ✗ absent | Optional[str] = None (Tier 2) |
| **Burden** | fact_proposition | required | N/A (B1 creates) | ✗ uses description | Optional[str] = None (Tier 2); engine's `description` kept as alias |
| **Burden** | shift_condition | required | N/A (B1 creates) | ✗ absent | Optional[str] = None (Tier 2) |
| **Burden** | description | ✗ absent in docs/03 | N/A | ✓ present | **Kept** as Optional[str] = None; backward compat for existing code |
| **ReportSection** | body (vs narrative_text) | narrative_text | N/A | body | **body** (keep engine name; narrative_text is a docs/03 alias) |
| **ReportSection** | section_index | ✗ absent | N/A | ✓ present | Kept (engine-specific, useful for ordering) |
| **ReportSection** | linked_issue_ids | ✗ (issue_id singular) | N/A | ✓ present (plural) | **linked_issue_ids** (plural; more flexible than singular) |
| **ReportSection** | linked_output_ids | absent | N/A | ✓ present | Kept |
| **ReportArtifact** | linked_output_ids | present | N/A | ✗ absent | Optional = [] (Tier 2) |
| **ReportArtifact** | linked_evidence_ids | present | N/A | ✗ absent | Optional = [] (Tier 2) |
| **ReportArtifact** | generated_at / created_at | generated_at | N/A | created_at | **created_at** (keep engine name) |
| **ReportArtifact** | extraction_metadata | present | N/A | ✗ absent | Optional = None (Tier 2) |
| **DiffEntry** | affected_party_ids | ✗ absent | ✗ absent | ✗ absent | **Removed** from spec (was incorrect) |
| **DiffSummary** | (wrapper object) | ✗ not a separate type | ✗ not a separate type | ✗ not a separate type | **Removed**; diff_summary stays as `Union[str, list[DiffEntry]]` inline on Scenario |
| **EvidenceIndex** | (shape) | N/A | artifact envelope (includes raw_materials, job_id etc.) | working format (case_id, evidence, extraction_metadata) | **Working format** (case_id, evidence, extraction_metadata); artifact envelope is a serialization detail for WorkspaceManager |

### Contents

**Enums:**
- `CaseType`: civil, criminal, admin (canonical; matches `indexing.schema.json`)
- `PromptProfile`: civil_loan (prompt template key; NOT a case_type value)
- `AccessDomain`: owner_private, shared_common, admitted_record
- `EvidenceStatus`: private, submitted, challenged, admitted_for_discussion
- `EvidenceType`: documentary, physical, witness_statement, electronic_data, expert_opinion, audio_visual, other
- `IssueType`: factual, legal, procedural, mixed
- `IssueStatus`: open, resolved, deferred
- `PropositionStatus`: unverified, supported, contradicted, disputed
- `BurdenStatus`: met, partially_met, not_met, disputed
- `StatementClass`: fact, inference, assumption
- `WorkflowStage`: case_structuring, procedure_setup, simulation_run, report_generation, interactive_followup
- `ProcedurePhase`: case_intake, element_mapping, opening, evidence_submission, evidence_challenge, judge_questions, rebuttal, output_branching
- `ChangeItemObjectType`: Party, Claim, Defense, Issue, Evidence, Burden, ProcedureState, AgentOutput, ReportArtifact
- `DiffDirection`: strengthen, weaken, neutral
- `ScenarioStatus`: pending, running, completed, failed

**Core objects:**
- `RawMaterial` (source_id, text, metadata)
- `Evidence` (evidence_id, case_id, owner_party_id, title, source, summary, evidence_type, target_fact_ids, target_issue_ids, access_domain, status, submitted_by_party_id, challenged_by_party_ids, admissibility_notes)
- `Claim` (claim_id, case_id, owner_party_id, case_type, title, claim_text, claim_category, target_issue_ids, supporting_fact_ids, supporting_evidence_ids, status)
- `Defense` (defense_id, case_id, owner_party_id, against_claim_id, defense_text, defense_category, target_issue_ids, supporting_fact_ids, supporting_evidence_ids, status)
- `FactProposition` (proposition_id, text, status: PropositionStatus = unverified, linked_evidence_ids)
- `Issue` (issue_id, case_id, title, issue_type: IssueType, parent_issue_id, related_claim_ids, related_defense_ids, evidence_ids, burden_ids, fact_propositions, status: IssueStatus = open, created_at, **description: Optional = None [Tier 2]**, **priority: Optional = None [Tier 2]**)
- `Burden` (burden_id, case_id, issue_id, **burden_party_id**, proof_standard, legal_basis, status: BurdenStatus = not_met, **description: Optional = None [back-compat]**, **burden_type: Optional = None [Tier 2]**, **fact_proposition: Optional = None [Tier 2]**, **shift_condition: Optional = None [Tier 2]**)
- `Party` (party_id, case_id, name, party_type, role_code, side, case_type, access_domain_scope, active)

**Aggregate artifacts:**
- `ClaimIssueMapping` (claim_id, issue_ids)
- `DefenseIssueMapping` (defense_id, issue_ids)
- `EvidenceIndex` (case_id, evidence: list[Evidence], extraction_metadata: Optional[dict] = None) — working format; NOT the artifact envelope
- `IssueTree` (case_id, run_id, job_id, issues, burdens, claim_issue_mapping, defense_issue_mapping, extraction_metadata)

**Report layer:**
- `KeyConclusion` (conclusion_id, text, statement_class: StatementClass, supporting_evidence_ids, supporting_output_ids = [])
- `ReportSection` (section_id, section_index, title, body, linked_issue_ids, linked_output_ids = [], linked_evidence_ids, key_conclusions)
- `ReportArtifact` (report_id, case_id, run_id, title, summary, sections, created_at, **linked_output_ids: list = [] [Tier 2]**, **linked_evidence_ids: list = [] [Tier 2]**, **extraction_metadata: Optional = None [Tier 2]**)
- `InteractionTurn` (turn_id, case_id, report_id, run_id, turn_index, question, answer, issue_ids, evidence_ids, statement_class, created_at, metadata)

**Scenario layer:**
- `ChangeItem` (target_object_type: ChangeItemObjectType, target_object_id, field_path, old_value, new_value)
- `DiffEntry` (issue_id, impact_description, direction: DiffDirection) — NO affected_party_ids (matches JSON Schema)
- `Scenario` (scenario_id, case_id, baseline_run_id, change_set: list[ChangeItem], diff_summary: Union[str, list[DiffEntry]], affected_issue_ids, affected_evidence_ids, status: ScenarioStatus) — NO separate DiffSummary wrapper

**Index references (from simulation_run):**
- `MaterialRef` (index_name="material_index", object_type, object_id, storage_ref)
- `ArtifactRef` (index_name="artifact_index", object_type, object_id, storage_ref)
- `InputSnapshot` (material_refs, artifact_refs)

**Infrastructure:**
- `LLMClient` (Protocol): `async create_message(*, system: str, user: str, model: str = "claude-sonnet-4-20250514", temperature: float = 0.0, max_tokens: int = 4096, **kwargs) -> str`
- `ExtractionMetadata` (model_used, temperature, timestamp, prompt_profile, prompt_version, total_tokens) — note: `prompt_profile` persisted here for run replayability
- `Run` (run_id, case_id, workspace_id, scenario_id, trigger_type, input_snapshot: InputSnapshot, output_refs: list[Union[MaterialRef, ArtifactRef]], started_at, finished_at, status)

### What stays in each engine's schemas.py

LLM intermediate models only — `LLMEvidenceItem`, `LLMIssueItem`, `LLMBurdenItem`, `LLMReportOutput`, etc. These are engine-internal parsing types, not shared across engines.

Engine-specific wrapper types (e.g., `EvidenceIndexResult`, `ClaimDefenseResult`, `ProcedureSetupResult`, `ScenarioResult`) also stay in each engine's schemas.py, but they compose shared models from `engines/shared/models.py`.

Engine-specific `ExtractionMetadata` subtypes (e.g., issue_extractor's version with `total_claims_processed`) stay in engine schemas.py and extend the shared `ExtractionMetadata` or use `dict`.

### Migration rule

Each engine's `schemas.py`:
1. Delete all duplicate type definitions (Issue, Burden, IssueTree, EvidenceIndex, FactProposition, ClaimIssueMapping, DefenseIssueMapping, enums, etc.)
2. Add `from engines.shared.models import <types>`
3. Keep only LLM intermediate models and engine-specific wrappers
4. **No field renames needed in engine code** — shared model uses engine code field names (body, linked_issue_ids, created_at, etc.) with docs/03 extras as Optional

## 2. CaseWorkspace Persistence — `engines/shared/workspace_manager.py`

### Directory layout

```
workspace/{case_id}/
  workspace.json              # Thin index (metadata + artifact_index references)
  materials/
    raw_materials.json        # Input materials
  artifacts/
    evidence_index.json       # evidence_indexer output
    claim_defense.json        # claim_extractor output
    issue_tree.json           # issue_extractor output
    report.json               # report_generation output
    turns/
      turn_001.json           # interactive_followup outputs
      turn_002.json
    scenarios/
      scenario_{id}.json      # simulation_run outputs
  runs/
    run_{id}.json             # Run snapshots
```

### workspace.json structure

Conforms to `schemas/case/case_workspace.schema.json`:

```json
{
  "workspace_id": "ws-civil-loan-001",
  "case_id": "case-civil-loan-001",
  "case_type": "civil",
  "current_workflow_stage": "report_generation",
  "material_index": {
    "Evidence": [{"object_type": "Evidence", "object_id": "evidence-001", "storage_ref": "artifacts/evidence_index.json"}],
    "Claim": [{"object_type": "Claim", "object_id": "claim-001", "storage_ref": "artifacts/claim_defense.json"}],
    "Defense": [{"object_type": "Defense", "object_id": "defense-001", "storage_ref": "artifacts/claim_defense.json"}],
    "Issue": [],
    "Burden": [],
    "Party": [],
    "ProcedureState": []
  },
  "artifact_index": {
    "AgentOutput": [],
    "ReportArtifact": [{"object_type": "ReportArtifact", "object_id": "report-001", "storage_ref": "artifacts/report.json"}],
    "InteractionTurn": [{"object_type": "InteractionTurn", "object_id": "turn-001", "storage_ref": "artifacts/turns/turn_001.json"}],
    "Scenario": []
  },
  "run_ids": ["run-001", "run-002"],
  "active_scenario_id": null,
  "status": "active"
}
```

### WorkspaceManager interface

```python
class WorkspaceManager:
    def __init__(self, base_dir: Path, case_id: str)

    # Lifecycle
    def init_workspace(self, case_type: str) -> dict
    def load_workspace(self) -> dict | None

    # Run persistence (explicit — called by pipeline, not hidden inside save_*)
    def save_run(self, run: Run) -> None
        # 1. Write runs/run_{id}.json atomically
        # 2. Append run_id to workspace.json.run_ids
        # 3. Atomic workspace.json update
    def load_run(self, run_id: str) -> Run | None

    # Artifact persistence (does NOT auto-save the Run)
    def save_evidence_index(self, evidence_index: EvidenceIndex) -> None
        # 1. Write artifacts/evidence_index.json
        # 2. Update workspace.json material_index.Evidence refs
    def save_claims_defenses(self, claims: list[Claim], defenses: list[Defense]) -> None
        # 1. Write artifacts/claim_defense.json
        # 2. Update workspace.json material_index.Claim + Defense refs
    def save_issue_tree(self, issue_tree: IssueTree) -> None
    def save_report(self, report: ReportArtifact) -> None
    def save_interaction_turn(self, turn: InteractionTurn) -> None
    def save_scenario_result(self, scenario: Scenario) -> None

    # Artifact loading (for checkpoint resume)
    def load_evidence_index(self) -> EvidenceIndex | None
    def load_claims_defenses(self) -> tuple[list[Claim], list[Defense]] | None
    def load_issue_tree(self) -> IssueTree | None
    def load_report(self) -> ReportArtifact | None

    # Stage advancement
    def advance_stage(self, stage: WorkflowStage) -> None
```

### Run persistence contract

**Who creates the Run**: The pipeline orchestrator (`pipeline.py`), NOT the engines and NOT the WorkspaceManager.

**Sequence per stage** (example: stage 2 case_structuring):
```python
# 1. Pipeline creates Run before engine execution
run = Run(
    run_id=f"run-{uuid4().hex[:8]}",
    case_id=case_id,
    workspace_id=ws.workspace_id,
    trigger_type="case_structuring",
    input_snapshot=InputSnapshot(material_refs=[...]),
    output_refs=[],  # filled after engines complete
    started_at=now_iso(),
    status="running",
)

# 2. Engines execute (parallel)
evi_result, claim_result = await asyncio.gather(...)

# 3. Pipeline fills output_refs
run.output_refs = [
    MaterialRef(object_type="Evidence", object_id=..., storage_ref="artifacts/evidence_index.json"),
    MaterialRef(object_type="Claim", object_id=..., storage_ref="artifacts/claim_defense.json"),
]
run.finished_at = now_iso()
run.status = "completed"

# 4. Pipeline calls WorkspaceManager in sequence (single-process, no lock)
ws_mgr.save_evidence_index(evi_result)
ws_mgr.save_claims_defenses(claim_result.claims, claim_result.defenses)
ws_mgr.save_run(run)  # explicit, separate from artifact writes
ws_mgr.advance_stage(WorkflowStage.case_structuring)
```

**Atomicity**: Each `save_*` and `save_run` is individually atomic (write `.tmp` then rename). The four calls in step 4 are NOT jointly atomic — if the process crashes between `save_evidence_index` and `save_run`, the artifacts exist but the run doesn't. This is safe because:
- Checkpoint resume checks artifact files, not runs
- The orphaned artifacts will be linked to a new Run on re-execution
- v1's Job state machine will provide full transactional semantics

### Design constraints

- Every `save_*` and `save_run` call atomically writes its file (`.tmp` + rename) and updates workspace.json
- `storage_ref` values are relative paths from workspace root
- `load_*` returns `None` if the artifact file does not exist (checkpoint miss)
- `load_*` validates `case_id` matches workspace's `case_id` and JSON is well-formed; raises on mismatch
- v0.5 is single-process — no file locking needed; parallel stage (step 2) collects both results in memory then writes sequentially
- `save_run` appends to `workspace.json.run_ids` and writes `runs/run_{id}.json`; idempotent (re-saving same run_id overwrites)

## 3. Claim Extractor — `engines/case_structuring/claim_extractor/`

### Directory structure

```
engines/case_structuring/claim_extractor/
  __init__.py
  schemas.py          # LLM intermediate models + ClaimDefenseResult wrapper
  extractor.py        # ClaimExtractor main class
  validator.py        # ValidationResult/Report pattern
  prompts/
    __init__.py       # PROMPT_REGISTRY
    civil_loan.py     # 民间借贷 prompts
  tests/
    __init__.py
    test_contract.py
    test_extractor.py
```

### Input / Output

```python
# Input: same raw materials as evidence_indexer
input: list[RawMaterial]  # from engines/shared/models.py

# Output
class ClaimDefenseResult:  # in claim_extractor/schemas.py
    case_id: str
    claims: list[Claim]       # from engines/shared/models.py
    defenses: list[Defense]   # from engines/shared/models.py
    extraction_metadata: ExtractionMetadata
```

### ClaimExtractor class

```python
class ClaimExtractor:
    def __init__(
        self,
        llm_client: LLMClient,
        prompt_profile: str = "civil_loan",  # prompt template key, NOT case_type
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        max_retries: int = 3,
    )

    async def extract(
        self,
        materials: list[RawMaterial],
        case_id: str,
        owner_party_id: str,
        counter_party_id: str,
        case_slug: str = "case",
    ) -> ClaimDefenseResult
```

### Contract guarantees

- Every Claim has `owner_party_id` and non-empty `claim_text`
- Every Defense points to a valid `against_claim_id`
- claim_id format: `claim-{case_slug}-{seq:03d}`
- defense_id format: `defense-{case_slug}-{seq:03d}`
- Atomic batch processing (all-or-nothing, consistent with evidence_indexer)
- At least one Claim (civil loan always has plaintiff claims); Defense list may be empty
- Source coverage: best-effort — sources containing only evidence without claims/defenses are permitted (e.g., bank statements, transfer records); NOT every source_id must map to a Claim or Defense

### Pipeline relationship

evidence_indexer and claim_extractor run **in parallel** on the same `list[RawMaterial]` — no dependency between them. Both feed into issue_extractor.

## 4. Pipeline Orchestrator — `engines/pipeline.py`

### Interface

```python
class PipelineResult:
    workspace: dict           # Final workspace.json state
    evidence_index: EvidenceIndex
    claims: list[Claim]
    defenses: list[Defense]
    issue_tree: IssueTree
    report: ReportArtifact
    runs: list[Run]

async def run_pipeline(
    llm_client: LLMClient,
    raw_materials: list[RawMaterial],
    case_id: str,
    case_slug: str,
    owner_party_id: str,
    counter_party_id: str,
    workspace_dir: Path,
    case_type: str = "civil",            # canonical CaseType enum (civil/criminal/admin)
    prompt_profile: str = "civil_loan",  # prompt template key (selects prompts/ module)
    force_rerun: bool = False,
) -> PipelineResult
```

### Execution flow

```
Step 1: WorkspaceManager.init_workspace() or load_workspace()

Step 2: Checkpoint — evidence_index and claim_defense exist?
  YES → load from files
  NO  → parallel execution:
        ├─ evidence_indexer.index(materials) → EvidenceIndex
        └─ claim_extractor.extract(materials) → ClaimDefenseResult
        → save_evidence_index() + save_claims_defenses()
        → advance_stage("case_structuring")

Step 3: Checkpoint — issue_tree exists?
  YES → load from file
  NO  → issue_extractor.extract(claims, defenses, evidence)
        → save_issue_tree()

Step 4: Checkpoint — report exists?
  YES → load from file
  NO  → report_generator.generate(issue_tree, evidence_index)
        → save_report()
        → advance_stage("report_generation")

  # v1: procedure_setup goes here (between step 3 and step 4)

Step 5: Return PipelineResult
```

### Design details

- **Parallel stage**: Step 2 uses `asyncio.gather(evidence_indexer.index(...), claim_extractor.extract(...))`
- **interactive_followup**: Not in pipeline — called on-demand after pipeline completes; each call saves via `save_interaction_turn()`
- **simulation_run**: Not in pipeline — optional sidecar called on-demand; each call saves via `save_scenario_result()`
- **Run generation**: Each stage creates a Run object; `trigger_type` labels the stage (e.g., `"case_structuring"`, `"report_generation"`). `input_snapshot` uses `material_refs` + `artifact_refs` per `indexing.schema.json`. `output_refs` uses a unified ref that can point to EITHER material_index or artifact_index entries (see Schema Migration below)
- **force_rerun**: When True, delete all artifact files under workspace, reset workspace.json to initial state, then re-execute everything from step 2
- **Error handling**: On any engine failure (LLM error, validation error, I/O error), the pipeline raises with the stage name and original exception. workspace.json retains `current_workflow_stage` set to the last *completed* stage and all completed artifacts remain on disk. Next run (without force_rerun) automatically resumes from the failed stage.
- **Parallel stage failure**: If evidence_indexer succeeds but claim_extractor fails (or vice versa) in step 2, neither result is saved — the entire stage is retried on next run. This keeps the "all-or-nothing per stage" invariant simple.

### Explicitly not done in v0.5

- No Job state machine (v1)
- No concurrency locks (v0.5 is single-process)
- No procedure_setup call (v1)
- No retry orchestration (each engine handles its own retries)

## 5. procedure_setup Disposition

### Decision

v0.5 pipeline does not call procedure_setup. Code is preserved intact.

### Actions

- `engines/procedure_setup/schemas.py` migrates shared types to `from engines.shared.models import ...` (same as all other engines)
- `pyproject.toml` testpaths includes procedure_setup tests (so they continue passing)
- `pipeline.py` has a comment marker: `# v1: procedure_setup goes here`
- No contract document created for procedure_setup in v0.5

### v1 upgrade path

When v1 introduces multi-role adversarial interaction:
1. Pipeline inserts `procedure_planner.plan()` after issue_extractor
2. ProcedureState[] constrains simulation_run's role permissions and round progression
3. report_generation consumes ProcedureState to generate a "procedure configuration and timeline" section

## 6. Complete Architecture Overview

### File structure after correction

```
engines/
  shared/
    __init__.py
    models.py                  # [NEW] All shared Pydantic models
    json_utils.py              # [EXISTING] JSON parsing utilities
    llm_client.py              # [NEW] LLMClient Protocol, single definition
    workspace_manager.py       # [NEW] CaseWorkspace read/write
  case_structuring/
    evidence_indexer/          # [MODIFIED] schemas.py imports from shared
    claim_extractor/           # [NEW] Claim/Defense extraction
    issue_extractor/           # [MODIFIED] schemas.py imports from shared
  procedure_setup/             # [MODIFIED] schemas.py imports from shared; not in v0.5 pipeline
  report_generation/           # [MODIFIED] schemas.py imports from shared
  simulation_run/              # [MODIFIED] schemas.py imports from shared; optional sidecar
  interactive_followup/        # [MODIFIED] schemas.py imports from shared; on-demand post-pipeline
  pipeline.py                  # [NEW] Functional pipeline with checkpoints
```

### Data flow (v0.5 complete pipeline)

```
Raw materials (list[RawMaterial])
    │
    ├──→ evidence_indexer.index()  ──→ EvidenceIndex ──┐
    │                                                   │
    └──→ claim_extractor.extract() ──→ claims[], defenses[]
                                                        │
                    ┌───────────────────────────────────┘
                    ↓
         issue_extractor.extract(claims, defenses, evidence)
                    ↓
              IssueTree (with burdens)
                    ↓
         report_generator.generate(issue_tree, evidence_index)
                    ↓
             ReportArtifact
                    ↓
    ┌───────────────┼─────────────────────┐
    ↓               ↓                     ↓
 [done]    followup.respond()     simulation.simulate()
           (on-demand, multi-turn) (on-demand, what-if)
```

Each stage completion: WorkspaceManager writes artifact file + updates workspace.json.

## 7. Schema Migration Scope

### What this spec migrates

1. **Pydantic models**: Create `engines/shared/models.py` as single source; all engine `schemas.py` import from it
2. **JSON Schemas**: Fix known inconsistencies (B1–B3 below) but do NOT rewrite all JSON Schemas from scratch
3. **`indexing.schema.json`**: Extend `output_refs` to accept both `material_ref` and `artifact_ref` (see below)

### Run.output_refs fix

**Problem**: `output_refs` in `run.schema.json` is typed as `array<artifact_ref>`, but stage 2 outputs (Evidence, Claim, Defense) and stage 3 outputs (Issue, Burden) are `material_index` objects, not `artifact_index` objects. Run cannot reference its own outputs.

**Fix**: Change `output_refs` to accept a union of `material_ref | artifact_ref`:

```json
"output_refs": {
  "type": "array",
  "items": {
    "oneOf": [
      { "$ref": "#/$defs/material_ref" },
      { "$ref": "#/$defs/artifact_ref" }
    ]
  }
}
```

This means:
- Stage 2 Run: `output_refs` contains `material_ref` entries pointing to Evidence, Claim, Defense in `material_index`
- Stage 3 Run: `output_refs` contains `material_ref` entries pointing to Issue, Burden in `material_index`
- Stage 4 Run: `output_refs` contains `artifact_ref` entry pointing to ReportArtifact in `artifact_index`

### What this spec does NOT migrate

- No new JSON Schema files beyond `burden.schema.json` (B1)
- No changes to `case_workspace.schema.json` structure (only fix field names)
- No changes to `job.schema.json` (v1)
- `evidence_index.schema.json` and `issue_tree.schema.json` field drift is documented but deferred to a dedicated schema alignment pass after B1-B6

### case_type vs prompt_profile convention

| Concept | Key | Values | Where used |
|---------|-----|--------|------------|
| Case type (schema-level) | `case_type` | `civil`, `criminal`, `admin` | workspace.json, JSON Schemas, Pydantic enums |
| Prompt profile (engine-level) | `prompt_profile` | `civil_loan`, (future: `criminal_fraud`, ...) | Engine constructors, `prompts/` module selection |

Rules:
- `case_type` appears in persisted data (workspace.json, JSON Schemas, Pydantic enums).
- `prompt_profile` is NOT stored in workspace.json (it is not a workspace property).
- `prompt_profile` IS persisted in `ExtractionMetadata.prompt_profile` on every engine output, so each Run's artifacts record which prompt was used. This ensures replayability without polluting the workspace schema.

## Blocker Fixes (Pre-Implementation)

Before implementing the above architecture, these blockers must be fixed **in this order** (dependencies flow downward):

1. **B1**: Create missing `schemas/case/burden.schema.json` — unblocks B2 and B5
2. **B2**: Unify Burden field name — `bearer_party_id` → `burden_party_id` everywhere — unblocks B5
3. **B3**: Align `EvidenceIndexResult` (Pydantic) with `EvidenceIndexArtifact` (JSON Schema) — unblocks B5
4. **B4**: Fix `pyproject.toml` testpaths to include all engine test directories — independent
5. **B7**: Extend `indexing.schema.json` `output_refs` to accept `material_ref | artifact_ref` — must precede B5 so shared `Run` type uses correct output_refs shape
6. **B5**: Create `engines/shared/models.py` (two-tier strategy per compatibility table above) and migrate all engine imports — depends on B1-B3 and B7 being done
7. **B6**: Fix `gold_burden_map.json` fixture to match unified field names — depends on B2

Dependency graph:
```
B1 ──→ B2 ──→ B5
B3 ──────────→ B5
B4 (independent)
B7 ──────────→ B5
B2 ──→ B6
```

## Out of Scope

- UI / frontend
- Multi-case-type support beyond prompt_profile
- Judge agent / multi-role adversarial
- Criminal / administrative case types
- External retrieval / OCR
- Online collaboration
- Job state machine (deferred to v1)
- procedure_setup integration (deferred to v1)
- Full JSON Schema rewrite (deferred to dedicated alignment pass)
