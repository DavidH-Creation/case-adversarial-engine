---
date: 2026-04-01
topic: v3-output-improvements
type: implementation-plan
status: active
revision: 2 (4-layer architecture + Codex adversarial review incorporated)
---

# v3 Output Improvements — 4-Layer Report Architecture

## Background

Three original features (F1 perspective output, F2 conditional scenarios, F3
evidence battle matrix) are unified into a single coherent output redesign.
The Codex adversarial review identified that treating them as independent
parallel changes was incorrect: F2 (removing fake probabilities) must land
first because F1 and F3 both consume `DecisionPathTree` output. The user's
4-layer architecture redesign makes the correct sequencing explicit.

**Codex HIGH-severity issues addressed here:**
- Issue 1: Sort criterion now uses `party_favored` only — no undefined "primary claimant"
- Issue 3: `ruling_tendency` falls back to `""` when `trigger_issue_ids` empty
- Issue 5: `scenario_condition` is **composed at render time** from existing fields
  (`trigger_condition + possible_outcome + fallback_path_id`) — no new LLM schema field
- Issue 6: `confidence_interval` also blanked when probability system is removed
- Issue 7: `path_ranking` is versioned — renamed to `path_order` in the renderer
- Issue 9: matrix renderer change is an explicit migration (old renderer renamed
  `render_matrix_markdown_v1` as snapshot baseline, new is `render_matrix_markdown`)

---

## Report Architecture (4 Layers)

```
report.md
│
├── Layer 1: 封面摘要 (Cover Summary)
│   ├── Block A — Neutral conclusion (one sentence, from overall_assessment)
│   ├── Block B — Client perspective card (only when --perspective is set)
│   ├── Block C — Conditional scenario snapshot (top 2 paths as if/then)
│   └── Block D — Evidence risk traffic light (green/yellow/red by stability)
│
├── Layer 2: 中立对抗内核 (Neutral Adversarial Core)
│   ├── 2.1 — Fact base (undisputed facts only, tagged 事实)
│   ├── 2.2 — Issue map (fixed 6-field template per issue)
│   ├── 2.3 — Evidence battle matrix (7-question table, evidence rows)
│   └── 2.4 — Conditional scenario tree (node-based if/then/else, no percentages)
│
├── Layer 3: 角色化输出 (Role-based Output)
│   └── Only rendered when --perspective is set
│       plaintiff: top claims, defendant attack chains, gaps to fill,
│                  trial sequence, claims to consider dropping
│       defendant: top defenses, plaintiff supplement risks,
│                  evidence to challenge first, motions to file
│
└── Layer 4: 附录 (Appendix)
    ├── 3-round adversarial transcripts
    ├── Evidence index
    ├── Amount calculation
    └── Hearing order / timeline
```

**Formatting rules (enforced in renderers):**
- Cards + tables + trees; no long paragraphs
- Every analytical statement tagged: `[事实]` `[推断]` `[假设]` `[建议]`
- Colors (green/yellow/red) = evidence stability only, NOT party stance
- Each issue fits in one fixed-field card

---

## F2 — Remove Pseudo-Precise Probabilities (must land first)

### Problem

`DecisionPath.probability: float` and `ConfidenceInterval` produce fake numeric
precision. The LLM guesses "0.73" with no statistical basis. This violates the
product principle of not making automatic win-probability claims.

### Implementation: compose at render time, no schema field added

`scenario_condition` is NOT a new Pydantic field. It is a pure render-time
composition from fields that already exist on `DecisionPath`:

```python
def _compose_scenario_condition(path: DecisionPath) -> str:
    """Compose a conditional branch sentence from existing path fields."""
    cond = path.trigger_condition or "条件满足"
    outcome = path.possible_outcome or "裁判结论待定"
    fallback = path.fallback_path_id
    if fallback:
        return f"若{cond}，则{outcome}；否则降级至路径 {fallback}。"
    return f"若{cond}，则{outcome}。"
```

### What actually changes

**`engines/simulation_run/decision_path_tree/prompts/` (3 files: civil_loan, labor_dispute, real_estate)**

Remove from the LLM prompt:
- The `probability` field instruction and JSON example
- The `probability_rationale` field instruction
- The `confidence_interval` field instruction
- Any mention of numeric probabilities

The LLM still produces `trigger_condition`, `possible_outcome`, `fallback_path_id`,
`party_favored`, `key_evidence_ids`, `trigger_issue_ids` — none of those change.

**`engines/simulation_run/decision_path_tree/generator.py`**

In `_build_path()`: stop populating `probability` from LLM item (set `0.0`
explicitly — field has a default). Stop calling `_compute_path_ranking` with
probability sort.

In `_compute_path_ranking()`: replace probability sort with:
1. `party_favored` (plaintiff paths first, then defendant, then neutral)
2. `len(key_evidence_ids)` descending
3. `path_id` alphabetical for stability

In `_build_path()`: when `verdict_block_active=False`, also blank
`confidence_interval` (was only blanked for True) — removing the field from
active use entirely. A blank `ConfidenceInterval` model is not emitted; the
field remains `None`.

**`engines/shared/models/pipeline.py`**

No schema changes needed. `probability` has `default=0.5` already.
`confidence_interval` has `default=None` already. They remain in the model for
backward compat (existing serialized outputs load fine), but are no longer
populated.

### Files touched (F2)

| File | Change |
|------|--------|
| `engines/simulation_run/decision_path_tree/prompts/civil_loan.py` | Remove probability/confidence_interval instructions |
| `engines/simulation_run/decision_path_tree/prompts/labor_dispute.py` | Same |
| `engines/simulation_run/decision_path_tree/prompts/real_estate.py` | Same |
| `engines/simulation_run/decision_path_tree/generator.py` | `probability=0.0`; new sort; blank confidence_interval always |
| `engines/simulation_run/decision_path_tree/tests/test_generator.py` | Update ranking tests for new sort order |

---

## F3 — Evidence Battle Matrix (7 questions per evidence)

### Redesign: evidence-centric, not issue-centric

The original plan had 7 columns per issue-row. The correct design is 7 questions
per **evidence** row. Each evidence piece is evaluated against 7 fixed questions.

### The 7 questions

| # | Column | Data Source |
|---|--------|-------------|
| 1 | 证明目标 (Target issues) | `evidence.target_issue_ids` → issue titles |
| 2 | 提交方 (Owner) | `evidence.owner_party_id` |
| 3 | 可采性 (Admissibility) | `evidence.admissibility_status` (clear/uncertain/weak/excluded) |
| 4 | 对方质疑 (Opposition challenge) | `evidence.admissibility_challenges` joined; or "无" |
| 5 | 补强证据 (Corroboration) | count of other evidences sharing same `target_issue_ids` |
| 6 | 稳定性 (Stability traffic light) | computed from `evidence_type` + `authenticity_risk` + `is_attacked_by` |
| 7 | 路径依赖 (Path dependency) | count of `DecisionPath.key_evidence_ids` containing this evidence_id |

### Traffic light computation (column 6)

```python
def _evidence_stability_light(ev: Evidence) -> str:
    """Return '🟢 绿' / '🟡 黄' / '🔴 红'."""
    # Red: authenticity explicitly disputed or excluded
    if ev.admissibility_status.value in ("excluded",):
        return "🔴 红"
    if ev.authenticity_risk and ev.authenticity_risk.value in ("high",):
        return "🔴 红"
    if ev.is_attacked_by:
        return "🔴 红"
    # Yellow: screenshots, single-party statements, uncertain admissibility
    if ev.evidence_type.value in ("witness_statement", "audio_visual"):
        return "🟡 黄"
    if ev.admissibility_status.value in ("uncertain", "weak"):
        return "🟡 黄"
    # Green: third-party verifiable
    return "🟢 绿"
```

### Schema changes

**`engines/report_generation/schemas.py`** — add new evidence-centric matrix schema
alongside (not replacing) `MatrixRow` / `IssueEvidenceDefenseMatrix`:

```python
class EvidenceBattleRow(BaseModel):
    evidence_id: str
    evidence_title: str
    target_issue_labels: list[str]   # resolved from issue tree
    owner: str                        # party_id
    admissibility: str               # admissibility_status.value
    opposition_challenges: list[str] # admissibility_challenges
    corroboration_count: int         # count of corroborating evidences
    stability_light: str             # 🟢 / 🟡 / 🔴 + label
    path_dependency_count: int       # how many decision paths cite this

class EvidenceBattleMatrix(BaseModel):
    rows: list[EvidenceBattleRow]
    total_evidence: int
    green_count: int
    yellow_count: int
    red_count: int
```

### Builder function

**`engines/report_generation/evidence_battle_matrix.py`** (new file):

```python
def build_evidence_battle_matrix(
    evidence_index: EvidenceIndex,
    issue_tree: IssueTree | None = None,
    decision_path_tree: DecisionPathTree | None = None,
) -> EvidenceBattleMatrix | None:
    ...

def render_evidence_battle_matrix_markdown(matrix: EvidenceBattleMatrix) -> str:
    ...
    # 7-column table header:
    # | 证据 | 证明目标 | 提交方 | 可采性 | 对方质疑 | 补强 | 稳定性 | 路径依赖 |
```

### Backward compat

The old `render_matrix_markdown` (issue-centric 5-col) is **not deleted**. It is
renamed `render_issue_matrix_markdown` and still called from the appendix layer.
The new 7-col evidence matrix goes in Layer 2.3 of the report.

### Files touched (F3)

| File | Change |
|------|--------|
| `engines/report_generation/schemas.py` | Add `EvidenceBattleRow` + `EvidenceBattleMatrix` |
| `engines/report_generation/evidence_battle_matrix.py` | New file: builder + renderer |
| `engines/report_generation/issue_evidence_defense_matrix.py` | Rename `render_matrix_markdown` → `render_issue_matrix_markdown` |
| `engines/report_generation/tests/test_evidence_battle_matrix.py` | New tests |
| `engines/report_generation/tests/test_matrix.py` | Update import: `render_issue_matrix_markdown` |

---

## F1 — Perspective-Aware Output (`--perspective`)

### Architecture

`--perspective` affects TWO places in the report:
1. **Layer 1 Block B** — a short "client perspective card" inserted in the cover
2. **Layer 3** — a full role-based output section

Both are pure data transformations; no LLM call.

### Data sources

```
plaintiff perspective:
  top_strengths    ← summary.plaintiff_strongest_arguments[:3]
  top_dangers      ← paths where party_favored="defendant" with most key_evidence_ids
  priority_actions ← action_recommendations filtered where role="plaintiff"[:3]
  gaps_to_fill     ← missing_evidence_report where missing_for_party_id=plaintiff_id

defendant perspective:
  top_defenses     ← summary.defendant_strongest_defenses[:3]
  plaintiff_risks  ← paths where party_favored="plaintiff" (what plaintiff can prove)
  evidence_to_challenge ← evidence with admissibility_status ∈ {uncertain, weak}
                          AND owner_party_id = plaintiff_id
  priority_actions ← action_recommendations filtered where role="defendant"[:3]

judge perspective (neutral):
  top_contested    ← issues where outcome_impact="high" AND status="open"[:3]
  strongest_per_side ← plaintiff top 1 + defendant top 1
  unresolved_gaps  ← unresolved_issues[:5]
```

### Schema

**`engines/report_generation/schemas.py`** — add:

```python
class Perspective(str, Enum):
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    JUDGE = "judge"
    NEUTRAL = "neutral"

class PerspectiveCard(BaseModel):
    perspective: Perspective
    top_strengths: list[str]          # max 3
    top_dangers: list[str]            # max 2
    priority_actions: list[str]       # max 3
    relevant_paths: list[str]         # path_ids (renamed from favorable_paths per Codex issue 2)
```

### New file

**`engines/report_generation/perspective_summary.py`**:

```python
def build_perspective_card(
    perspective: Perspective,
    adversarial_result: AdversarialResult,
    decision_path_tree: DecisionPathTree | None,
    action_recommendations: list | None,
    missing_evidence_report: list | None,
    issue_tree: IssueTree | None,
) -> PerspectiveCard:
    ...

def render_layer1_block_b(card: PerspectiveCard) -> str:
    """Render the cover summary perspective card (Layer 1 Block B)."""
    ...

def render_layer3(card: PerspectiveCard, perspective: Perspective) -> str:
    """Render the full role-based output (Layer 3)."""
    ...
```

### Files touched (F1)

| File | Change |
|------|--------|
| `engines/report_generation/schemas.py` | Add `Perspective` enum + `PerspectiveCard` model |
| `engines/report_generation/perspective_summary.py` | New file |
| `engines/report_generation/tests/test_perspective_summary.py` | New tests |
| `scripts/run_case.py` | Add `--perspective` arg; inject Layer 1 Block B + Layer 3 into report |

---

## Phase Execution Plan

**IMPORTANT: F2 must be implemented first** (Codex Issue 8 — F1 and F3 consume
the path tree that F2 redefines).

### Phase 1 — F2 Prompt + Generator Changes (no schema changes)

**Files (5):**
1. `engines/simulation_run/decision_path_tree/prompts/civil_loan.py`
2. `engines/simulation_run/decision_path_tree/prompts/labor_dispute.py`
3. `engines/simulation_run/decision_path_tree/prompts/real_estate.py`
4. `engines/simulation_run/decision_path_tree/generator.py`
5. `engines/simulation_run/decision_path_tree/tests/test_generator.py`

**Verification:** `python -m pytest engines/simulation_run/decision_path_tree/ -x -q`

---

### Phase 2 — F3 Schema + Evidence Battle Matrix (pure data layer)

**Files (5):**
1. `engines/report_generation/schemas.py` (add `EvidenceBattleRow` + `EvidenceBattleMatrix`)
2. `engines/report_generation/evidence_battle_matrix.py` (new file)
3. `engines/report_generation/issue_evidence_defense_matrix.py` (rename renderer)
4. `engines/report_generation/tests/test_evidence_battle_matrix.py` (new tests)
5. `engines/report_generation/tests/test_matrix.py` (update import)

**Verification:** `python -m pytest engines/report_generation/tests/ -x -q`

---

### Phase 3 — F1 Schemas + Perspective Layer (pure data layer)

**Files (3):**
1. `engines/report_generation/schemas.py` (add `Perspective` + `PerspectiveCard`)
2. `engines/report_generation/perspective_summary.py` (new file)
3. `engines/report_generation/tests/test_perspective_summary.py` (new tests)

**Verification:** `python -m pytest engines/report_generation/tests/ -x -q`

---

### Phase 4 — CLI + Report Integration (wire all layers)

**Files (1):**
1. `scripts/run_case.py` (add `--perspective` arg; restructure report.md output into 4 layers)

**Verification:** `python -m pytest -x -q` (full suite — zero regression required)

---

## Acceptance Criteria

| Feature | Criterion |
|---------|-----------|
| F2 | All 3 prompt files have no mention of `probability`, `probability_rationale`, `confidence_interval` |
| F2 | `generator._build_path()` always sets `probability=0.0`, `confidence_interval=None` |
| F2 | `path_ranking` sort is stable and deterministic (no probability dependency) |
| F2 | All existing decision_path_tree tests pass |
| F3 | `build_evidence_battle_matrix()` returns `EvidenceBattleMatrix` with correct 7-field rows |
| F3 | `render_evidence_battle_matrix_markdown()` produces table with exactly 7 columns |
| F3 | Old `render_issue_matrix_markdown()` still works (backward compat rename) |
| F3 | `stability_light` is one of `🟢 绿` / `🟡 黄` / `🔴 红` for every row |
| F1 | `build_perspective_card(perspective=Perspective.PLAINTIFF, ...)` returns non-empty card |
| F1 | `render_layer3()` returns non-empty markdown for plaintiff/defendant/judge |
| F1 | `--perspective absent` → no perspective output; full pipeline unchanged |
| All | `python -m pytest -x -q` passes all existing tests (zero regression) |

---

## Out of Scope

- No new LLM calls for F1 or F3
- No changes to `AdversarialSummary`, `AdversarialResult`, `EvidenceIndex` schemas
- `DecisionPath.probability` stays in model at `0.0` (backward compat for existing runs)
- No UI changes (report.md structure only)
- No changes to the API layer or DOCX generator
