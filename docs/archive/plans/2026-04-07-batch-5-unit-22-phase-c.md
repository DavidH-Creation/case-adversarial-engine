# Batch 5 — Unit 22 Phase C: Three-Enum Case-Type Neutralization

> **Status:** In progress (created 2026-04-07)
> **Branch:** `batch-5-phase-c-enum-neutralization`
> **Base:** `main` @ `ce69ec7` (Merge batch-4-followup: complete Unit 14 plugin interface)
> **Predecessor units:** Unit 22 Phase A (civil_loan amount-calc isolation), Phase B (`Party.litigation_history → dict`)
> **Predecessor batch:** Batch 4 (Unit 14 plugin interface, 8 plugins + 14 runner migrations)

---

## 1. Goal

Eliminate the last remaining case-type leakage in the shared model layer by physically
isolating three enums currently defined in `engines/shared/models/core.py` that carry
**民间借贷 (civil_loan)**-specific vocabulary:

| Enum                    | Members (civil_loan vocab)                                            | Where it leaks                                                                 |
|-------------------------|------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| `ClaimType`             | principal / interest / penalty / attorney_fee / other                  | `ClaimCalculationEntry` (already civil_loan-only)                               |
| `RepaymentAttribution`  | principal / interest / penalty                                         | `RepaymentTransaction` (already civil_loan-only)                                |
| `ImpactTarget`          | principal / interest / penalty / attorney_fee / credibility            | **`Issue.impact_targets: list[ImpactTarget]`** — pollutes the GENERIC Issue model |

`ClaimType` and `RepaymentAttribution` are already 100% used by civil_loan-only structures
(`ClaimCalculationEntry`, `RepaymentTransaction`); their removal from `core.py` is a pure
"move + re-export" refactor.

`ImpactTarget` is the **real problem**: the generic `Issue` model in
`engines/shared/models/analysis.py` declares
`impact_targets: list[ImpactTarget] = Field(default_factory=list)`, forcing every
case type (labor_dispute, real_estate, …) to file its 争点影响 against civil_loan
vocabulary. This is also a **latent semantic bug**: the `issue_impact_ranker` prompts
for `labor_dispute` and `real_estate` literally copy-paste the civil_loan allowed-values
list (verified at `engines/simulation_run/issue_impact_ranker/prompts/labor_dispute.py:24`
and `prompts/real_estate.py:25`).

After this batch:

1. The three enums physically live in `engines/shared/models/civil_loan.py`.
2. They are still importable as `from engines.shared.models import X` (re-export preserved).
3. **No new deep imports** of the form `from engines.shared.models.core import (ClaimType|RepaymentAttribution|ImpactTarget)` are allowed (verified 0 hits at start of batch).
4. The generic `Issue.impact_targets` is weakened to `list[str]`, so labor_dispute / real_estate can land their own domain vocabulary without depending on civil_loan-named enum members.
5. `CaseTypePlugin` Protocol gains an optional `allowed_impact_targets(case_type) -> set[str]` method; the ranker calls it through the plugin instead of hard-coding the civil_loan set in `_resolve_impact_targets`.
6. labor_dispute / real_estate prompts and plugin allowed-sets are updated to legally-grounded domain vocabulary (see §5).

---

## 2. Pinned design decisions

These six questions were resolved before this batch began. Recording them here so future
sessions can audit the rationale.

### Q1 — Where do the three enums physically live after the move?
**Decision:** `engines/shared/models/civil_loan.py` (the existing physical-isolation
module, already home to `LoanTransaction`, `RepaymentTransaction`, `ClaimCalculationEntry`,
`LitigationHistory`, etc.). One file, one place. Do not introduce a new
`engines/shared/models/civil_loan_enums.py` — that would be ceremony with no payoff.

### Q2 — How are they re-exported, and what is forbidden?
**Decision: Option 1.** The enums are *defined* in `civil_loan.py` and *re-exported*
from `engines/shared/models/__init__.py`. The shallow path
`from engines.shared.models import ClaimType` continues to work. The deep paths
`from engines.shared.models.core import (ClaimType|RepaymentAttribution|ImpactTarget)`
are **forbidden** going forward — they will break loudly because the symbols no longer
exist in `core.py`. Verified before starting: 0 such imports today.

### Q3 — Should `Issue` validate that values in `impact_targets` come from a permitted set?
**Decision: No.** The Issue model stays maximally neutral. Validation lives in the
**ranker layer** (`_resolve_impact_targets`), which already filters unknown strings
before they reach `Issue`. Keeping the model passive is the whole point of the refactor:
case-type neutrality means "the generic model accepts any string and the case-type plugin
decides what is legal".

### Q4 — What is the legally-grounded vocabulary for labor_dispute and real_estate?
**Decision (researched against highest-court judicial interpretations):**

#### civil_loan (unchanged)
`principal / interest / penalty / attorney_fee / credibility`

#### labor_dispute (劳动争议)
Sources: 最高法《劳动争议司法解释一》、《劳动争议司法解释二》(法释〔2025〕12号),
《劳动合同法》§47、§87.

| Member                | 中文     | Legal basis                                                     |
|-----------------------|----------|-----------------------------------------------------------------|
| `wages`               | 工资     | 工资支付争议 — 劳动合同法 §30                                    |
| `overtime_pay`        | 加班费   | 加班工资争议 — 劳动合同法 §31, §44                              |
| `economic_compensation` | 经济补偿金 | 劳动合同法 §47 (单倍补偿)                                        |
| `damages`             | 二倍赔偿金 | 劳动合同法 §87 (违法解除二倍赔偿) / §38 兜底                      |
| `credibility`         | 整体可信度 | 与 civil_loan 共用：争点对整案可信度的冲击                        |

#### real_estate (房屋买卖合同纠纷)
Sources: 最高法《商品房买卖合同纠纷司法解释》(法释〔2003〕7号), 民法典合同编通则.

| Member                | 中文        | Legal basis                                                 |
|-----------------------|-------------|-------------------------------------------------------------|
| `specific_performance`| 继续履行    | 司法解释 §11 (判令交付/办理过户)                              |
| `refund`              | 返还购房款  | 司法解释 §8/§9 (合同解除时返还), 双倍返还定金                  |
| `liquidated_damages`  | 违约金      | 民法典 §585 / 商品房司法解释 §16                              |
| `damages`             | 损害赔偿    | 司法解释 §16 (实际损失填平)                                   |
| `credibility`         | 整体可信度  | 与 civil_loan 共用                                          |

`credibility` deliberately repeats across all three case types — it is the "整案可信度
冲击" axis used by `credibility_scorer` and is genuinely case-type agnostic.

### Q5 — Scope of Batch 5
**Decision:** Batch 5 covers C.1 through C.5b inclusively. Do **not** spin off a Batch 6
for the labor_dispute/real_estate vocabulary work — it has to ship with C.5a so that the
plugin interface and the case-type plugin instances land together.

### Q6 — Plan archival
**Decision:** Create `docs/archive/plans/2026-04-07-batch-5-unit-22-phase-c.md` (this
file). Phase C was originally a single bullet inside
`docs/archive/plans/2026-03-31-ce-brainstorm-phase4-5-assessment.md` with no
sub-decomposition; this document expands it into the six executable phases.

---

## 3. Blast radius assessment

| Symbol                  | Files referencing it (incl. tests/docs) | Code-only files     |
|-------------------------|-----------------------------------------|---------------------|
| `ImpactTarget`          | 9                                       | 7 (rest are docs)   |
| `RepaymentAttribution`  | 10                                      | 8                   |
| `ClaimType`             | 26                                      | 14 (12 are docs)    |

**Test impact:** estimated 7 (optimistic) to 37 (pessimistic) test assertions touched.
Original assessment doc warned of "1520 tests at risk" — that estimate was off by ~50×
because it conflated *all tests that import the shared models package* with *tests
that touch the three enums*.

**Critical pre-flight verifications (all PASS at batch start):**
- `from engines.shared.models.core import (RepaymentAttribution|ClaimType|ImpactTarget)` → **0 hits** ✅
- `is ImpactTarget\.` (identity comparison that would break after C.3) → **0 hits** ✅
- No `Issue.model_json_schema()` / `Issue.schema()` consumers depend on the
  `impact_targets` field having an enum-typed JSON schema — confirmed by reading
  `engines/simulation_run/issue_impact_ranker/schemas.py`, which builds its
  `_TOOL_SCHEMA` from `LLMIssueEvaluationOutput`, where `impact_targets` is **already**
  declared `list[str]`. The Issue model's JSON schema only matters for the workspace
  serialization layer, which round-trips strings either way.

---

## 4. Phase decomposition

Each phase is a single commit. After every commit, run
`LLM_MOCK=true python -m pytest -q` and verify the baseline (~2365 passing) is preserved
or grows (new tests added by C.5b will increase the count).

### C.1 — Move `RepaymentAttribution` to `civil_loan.py`

**Files touched (3):**
- `engines/shared/models/core.py` — delete `class RepaymentAttribution`
- `engines/shared/models/civil_loan.py` — add `class RepaymentAttribution`, drop the
  `RepaymentAttribution` from the `from engines.shared.models.core import (...)` block,
  add `"RepaymentAttribution"` to `__all__`
- `engines/shared/models/__init__.py` — move `RepaymentAttribution` from the
  `from .core import (...)` block to a new
  `from engines.shared.models.civil_loan import (RepaymentAttribution, ...)` block,
  keep it in the package `__all__`

**Verification:**
- `python -c "from engines.shared.models import RepaymentAttribution; print(RepaymentAttribution.principal)"` → `RepaymentAttribution.principal`
- `LLM_MOCK=true python -m pytest -q` → baseline preserved
- mypy + ruff clean

**Commit:** `refactor(models): C.1 physically isolate RepaymentAttribution to civil_loan (Unit 22 Phase C)`

### C.2 — Move `ClaimType` to `civil_loan.py`

**Files touched (3):**
- `engines/shared/models/core.py` — delete `class ClaimType`
- `engines/shared/models/civil_loan.py` — add `class ClaimType`, drop from the
  `core` import, add to `__all__`
- `engines/shared/models/__init__.py` — re-route `ClaimType`

**Verification:** same shape as C.1.

**Commit:** `refactor(models): C.2 physically isolate ClaimType to civil_loan (Unit 22 Phase C)`

### C.3 — **POINT OF NO RETURN**: weaken `Issue.impact_targets` to `list[str]`

**Files touched (4):**
- `engines/shared/models/analysis.py`
  - Remove `ImpactTarget` from the `from .core import (...)` block at line 25
  - Change `impact_targets: list[ImpactTarget] = Field(default_factory=list)` →
    `impact_targets: list[str] = Field(default_factory=list, description="Domain vocabulary terms; legal set is governed by the active CaseTypePlugin.allowed_impact_targets(case_type)")`
- `engines/simulation_run/issue_impact_ranker/ranker.py`
  - Remove `ImpactTarget` from imports at line 35
  - Rewrite `_resolve_impact_targets(raw: list[str]) -> list[str]` to filter against
    a *temporary* hard-coded civil_loan whitelist (this whitelist disappears in C.5a).
    The function MUST still drop unknown strings — that contract is intact.
- `engines/simulation_run/issue_impact_ranker/tests/test_ranker.py`
  - Line 32: drop `ImpactTarget` from imports
  - Line 447: change `{ImpactTarget.principal, ImpactTarget.interest}` → `{"principal", "interest"}`
- `engines/shared/tests/test_models_p0_1.py`
  - Lines 13, 31-36, 87, 96: replace `ImpactTarget.principal/.interest` literals with
    plain `"principal"`/`"interest"` strings; the `TestImpactTarget` class tests the
    enum's *value set* — keep that test using the enum (now imported from
    `engines.shared.models` which still re-exports it).

**Why C.3 is the point of no return:** Once `Issue.impact_targets` is `list[str]`, any
downstream code that expects an enum-typed list will fail. Reverting C.3 alone (without
also reverting C.4) would leave dead code.

**Verification:**
- `LLM_MOCK=true python -m pytest -q` → baseline preserved (the 2-3 enum-literal
  assertions update to string literals)
- `python -c "from engines.shared.models import Issue, ImpactTarget; i = Issue(issue_id='x', case_id='c', title='t', issue_type='factual', impact_targets=[ImpactTarget.principal, 'interest']); print(i.impact_targets)"` → `['principal', 'interest']` (verifies str enum coercion still works)
- mypy clean

**Commit:** `refactor(models): C.3 weaken Issue.impact_targets to list[str] for case-type neutrality (Unit 22 Phase C — POINT OF NO RETURN)`

### C.4 — Move `ImpactTarget` to `civil_loan.py`

**Files touched (3):**
- `engines/shared/models/core.py` — delete `class ImpactTarget`
- `engines/shared/models/civil_loan.py` — add `class ImpactTarget`, add to `__all__`
- `engines/shared/models/__init__.py` — re-route
- `engines/simulation_run/issue_impact_ranker/schemas.py` — drop the unused
  `ImpactTarget` from line 21 (it was a re-export but no consumer imports it from
  this module — verified by separate grep before this phase)

**Verification:** baseline preserved.

**Commit:** `refactor(models): C.4 physically isolate ImpactTarget to civil_loan (Unit 22 Phase C)`

### C.5a — Extend `CaseTypePlugin` Protocol with `allowed_impact_targets`

**Files touched (3):**
- `engines/shared/case_type_plugin.py`
  - Add an optional method to the Protocol:
    ```python
    def allowed_impact_targets(self, case_type: str) -> set[str]:
        """Return the set of legal impact_target string values for this case type.
        Implementations should return the case-type-specific vocabulary (e.g.
        civil_loan returns {principal, interest, penalty, attorney_fee, credibility};
        labor_dispute returns {wages, overtime_pay, economic_compensation, damages, credibility}).
        Defaults to the civil_loan set on RegistryPlugin if a registry entry does not
        override this method, preserving backward compatibility for the existing
        engines that haven't migrated yet."""
        ...
    ```
  - Add a concrete default implementation on `RegistryPlugin` returning the civil_loan
    set, but checking the registry entry first: if the entry exposes
    `ALLOWED_IMPACT_TARGETS`, return that; else default. This makes the *existing*
    civil_loan prompt module the source of truth without requiring any change there.
- `engines/simulation_run/issue_impact_ranker/prompts/civil_loan.py` — add a
  module-level constant `ALLOWED_IMPACT_TARGETS = frozenset({"principal", "interest", "penalty", "attorney_fee", "credibility"})`
  so `RegistryPlugin` can pick it up.
- `engines/simulation_run/issue_impact_ranker/ranker.py`
  - Replace the hard-coded civil_loan whitelist in `_resolve_impact_targets` with
    a runtime call: `plugin.allowed_impact_targets(self._case_type)` (cache it on
    `__init__` to avoid repeated lookups)
  - The validation contract is unchanged: any value not in the case-type-specific
    set is silently dropped (this is the "宽松" behavior already in place)

**Verification:**
- baseline preserved
- New unit test in `engines/shared/tests/test_case_type_plugin.py` (or a sibling) that
  verifies `RegistryPlugin.allowed_impact_targets("civil_loan")` returns the civil_loan
  set, and that an unknown case_type returns the civil_loan default

**Commit:** `feat(plugin): C.5a add allowed_impact_targets to CaseTypePlugin protocol (Unit 22 Phase C)`

### C.5b — Land legally-grounded vocabulary for labor_dispute and real_estate

**Files touched (4):**
- `engines/simulation_run/issue_impact_ranker/prompts/labor_dispute.py`
  - Replace civil_loan vocab string in the system prompt at line 24 (the
    `允许值：principal / interest / penalty / attorney_fee / credibility` line)
    with `允许值：wages / overtime_pay / economic_compensation / damages / credibility`
  - Update the example JSON at line 75 (currently `["principal", "credibility"]`) to
    use labor_dispute vocab, e.g. `["economic_compensation", "credibility"]`
  - Add `ALLOWED_IMPACT_TARGETS = frozenset({"wages", "overtime_pay", "economic_compensation", "damages", "credibility"})`
- `engines/simulation_run/issue_impact_ranker/prompts/real_estate.py`
  - Replace civil_loan vocab string at line 25 with `允许值：specific_performance / refund / liquidated_damages / damages / credibility`
  - Update example JSON at line 76 (currently `["principal", "penalty"]`) to e.g.
    `["specific_performance", "liquidated_damages"]`
  - Add `ALLOWED_IMPACT_TARGETS = frozenset({"specific_performance", "refund", "liquidated_damages", "damages", "credibility"})`
- `engines/shared/tests/test_case_type_plugin.py` (or a new test file) — add tests:
  - `RegistryPlugin.allowed_impact_targets("labor_dispute")` → labor_dispute set
  - `RegistryPlugin.allowed_impact_targets("real_estate")` → real_estate set
- Inspect `tests/acceptance/golden_artifacts/{labor_dispute,real_estate}/` if they
  exist; if any golden ranked-issue JSON contains civil_loan vocabulary in the
  `impact_targets` field, regenerate or update the golden expectations.

**Verification:**
- baseline preserved
- New `allowed_impact_targets` tests pass
- mypy + ruff clean

**Commit:** `feat(case_types): C.5b land legally-grounded impact_target vocabulary for labor_dispute / real_estate (Unit 22 Phase C)`

---

## 5. Push window discipline

C.3 + C.4 form an atomic pair: reverting C.3 (the contract weakening) without also
reverting C.4 (the move) would leave `Issue.impact_targets: list[str]` with no consumer
of `ImpactTarget` enum members anywhere, dead code in `civil_loan.py`, and a confusing
git history. Both must be in the same push window. Practically: do not pause for
overnight review between C.3 and C.4. C.5a/C.5b can pause naturally between phases.

---

## 6. Adversarial review checklist (after C.5b)

Same rigor level as Batch 4 review. Look for:

1. **Did any consumer slip through?** Re-grep all three enum names; expect every
   match to be either inside `civil_loan.py`, or going through the `__init__.py`
   re-export, or in `docs/`.
2. **Did the deep-import ban hold?** Re-grep `from engines.shared.models.core import`
   for the three names — must be 0.
3. **Does the ranker still drop unknown values?** Add an explicit test:
   `IssueImpactRanker(case_type="civil_loan")` evaluating an LLM response that includes
   the labor_dispute member `"wages"` in `impact_targets` should silently drop `"wages"`.
4. **Did labor_dispute / real_estate prompts lose any other civil_loan leakage?** Read
   them end-to-end; the few-shot examples loaded via `load_few_shot_text` may also
   reference principal/interest.
5. **Does `Issue.model_json_schema()` still serialize cleanly?** Confirm the JSON schema
   for `impact_targets` is now `{"type": "array", "items": {"type": "string"}}` (no
   enum constraint) and that no downstream tooling depends on the old enum constraint.
6. **Does the pre-existing `pipeline.py` re-export of civil_loan still compile?**
   pipeline.py imports `from engines.shared.models.civil_loan import (...)`. After C.4,
   civil_loan.py imports from itself for `ImpactTarget` etc. — make sure no circular
   import sneaks in.
7. **mypy `--strict` on the touched modules** still passes.
8. **Did the new `ALLOWED_IMPACT_TARGETS` constants get tested for completeness?**
   Each set should be exactly the documented size; missing or extra members are caught
   by an explicit assertion.

---

## 7. Out of scope (deferred to follow-on units)

- Migrating other engines' prompt modules (`adversarial`, `decision_path_tree`,
  `attack_chain_optimizer`, etc.) to use the new `ALLOWED_IMPACT_TARGETS`. Those
  engines do not currently consume `Issue.impact_targets` directly; the
  `issue_impact_ranker` is the single producer, so this batch is sufficient to
  achieve case-type neutrality at the model layer. A separate batch can sweep the
  prompt modules later if/when other engines start producing impact_targets too.
- Adding a stronger model_validator to Issue (Q3 explicitly rejected this — keep
  the model passive).
- Renaming any prompt files. The file names (`labor_dispute.py`, `real_estate.py`)
  remain stable.
