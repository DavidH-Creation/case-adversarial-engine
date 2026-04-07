# Layer 4 Handoff — Pause Point Before Batch 6.0a

**Date**: 2026-04-07
**Author**: Claude (epic-williamson worktree)
**Audience**: future-me / next conversation
**Purpose**: clean pause point so we can resume Layer 4 work without context loss

---

## 1. Where we are right now

**Layer 3: COMPLETE.** All of Batches 1-5 + Batch 4 follow-up have shipped to `main`. Phase C of Unit 22 (case-type enum neutralization) was the last substantive code change — landed in commit `50f28fe` (merge), then docs work landed on top.

**Layer 4: PLANNING + SPIKE COMPLETE. NO CODE WRITTEN YET.**

We are at the pause point **immediately before Batch 6.0a (coupling audit)**. The plan v2 has been written and codex-reviewed; the 6.1.0 prompt-inheritance spike has been run and the verdict is in. The next click is to actually start the audit batch — but we are stopping here so the user can switch projects.

---

## 2. Artifacts inventory (Layer 4 planning + spike)

| File | Commit | Purpose |
|---|---|---|
| `docs/plans/2026-04-07-layer-4-criminal-admin-plan.md` | `4bdefda` | Plan v2 — restructured per codex review. The source of truth for Layer 4 strategy. |
| `docs/plans/2026-04-07-layer-4-criminal-admin-plan.review.md` | `4bdefda` | Codex adversarial review of plan v1 (~11k lines). Reference only — search for I-markers and Critical/Important risk labels. |
| `docs/plans/2026-04-07-layer-4-spike-6.1.0-report.md` | `e03e92d` | Spike 6.1.0 result. Verdict + cost curves + next-step instructions. **Read this first when resuming.** |
| `docs/plans/2026-04-07-layer-4-HANDOFF.md` | (this commit) | This file. |

The hand-written `_criminal_base.py` + `intentional_injury.py` source from the spike lives in `/tmp/spike/intentional_injury_ranker_prompt.md` — **not committed**, it's scratch. The full source is also inlined in the spike report's prompt body section, so it's archived even if `/tmp/spike/` gets cleaned.

---

## 3. Spike verdict summary

**Verdict: OK with one tweak.** Two-layer inheritance (family base + subtype override) is approved for Batch 6.1+.

- Civil baseline pairwise reuse: **75.0% / 75.9% / 83.7%** (labor↔civil_loan / real_estate↔civil_loan / labor↔real_estate). Worst pair clears the 60% gate with 15-point margin.
- Criminal first-subtype (`intentional_injury` × `issue_impact_ranker`) measured **75.4% reuse / 24.6% override rate**, with **purely additive** override structure (zero subtraction, zero leak risk).
- Cost curves: 2-layer crosses flat at k=2 subtypes per family per engine; saves **~40% LOC at k=3** (Layer 4 MVP scope) and rises with subtype count.
- The "tweak" is a mandatory mini-batch **6.1.0b** (civil_loan template alignment, <1 day) so all three civil prompts match the Phase C.5b shape before the criminal base copies their structural decisions.

**Key non-obvious finding**: headline reuse % alone is misleading. The labor-as-base shortcut scores higher (~82%) than the purpose-built criminal base (~75%) but is operationally fragile because its override is subtractive. **Override structure (additive vs subtractive) matters more than the percent.** This is the most important sentence in the report.

---

## 4. Next-step instructions (when you resume)

**Spike verdict was "OK with tweak" → path (a) applies: direct to Batch 6.0a coupling audit.**

### First-five-minutes routine when resuming
1. **Read the spike report top-to-bottom** (`docs/plans/2026-04-07-layer-4-spike-6.1.0-report.md`). It's ~190 lines and contains everything you need to resume. Specifically confirm you understand §"6. Next step" — that's your starting line.
2. **Skim plan v2 §"问题 5" and §"Reality Check"** (`2026-04-07-layer-4-criminal-admin-plan.md`, lines ~330-360 and ~580-650). These are the sections that the spike result mutates.
3. **Run `git log --oneline main -10`** to confirm `e03e92d` is still HEAD (the spike commit) and that nobody has landed anything in between.
4. **Clean up worktrees** (see §5 below — this is the dominant performance pain point right now).
5. **Then** start Batch 6.0a.

### Folding the spike result into plan v2 (do this BEFORE 6.0a kicks off)
These are in-place edits to `2026-04-07-layer-4-criminal-admin-plan.md`. Should take <30 min:

1. **§"问题 5"** (around line 348-356): strike the "TBD pending 6.1.0 spike" placeholder. Replace with the measured numbers from the spike report (civil reuse 75-84% / criminal 75.4% / structural verdict = additive scales). Add a one-line forward-pointer to the spike report.
2. **§"总代码量估算"** (around line 354-356): collapse the conditional range. Replace "if inheritance ~10k-12k / if flat ~18k-22k" with **"6,000-13,000 new LOC (anchor at lower end)"** based on spike Step 4 numbers.
3. **§"Reality Check 节点"** (around line 617-647): tighten the realistic estimate from 18-22 wk to **17-19 wk** in the table. Update the 3-paragraph "Optimistic/Realistic/Pessimistic" assumptions to reflect "spike cleared the gate" rather than "pending spike".
4. **§"最大的未决问题"** (around line 680-692): strike the "6.1.0 spike result will decide ..." paragraph entirely. Replace with the new sole open question: **6.0b family-neutralization depth**.

### Batch 6.0a starting commands (when you actually begin)
6.0a is the **coupling audit** — it's almost entirely read-only investigation. The acceptance criterion (per plan v2) is a written audit deliverable that enumerates every shared-model and engine-layer hardcoded civil semantic.

Suggested first commands:
```bash
# create batch worktree
git worktree add ../batch-6.0a-audit -b batch-6.0a-coupling-audit main

# scope: identify all civil-shaped touch points in shared models
grep -rn -E "civil_loan|labor_dispute|real_estate" engines/shared/models/
grep -rn -E "principal|interest|wages|specific_performance" engines/shared/

# scope: identify all civil-shaped touch points in procedure & pretrial
grep -rn -E "原告|被告|plaintiff|defendant" engines/simulation_run/procedure_setup/
grep -rn -E "原告|被告|plaintiff|defendant" engines/simulation_run/pretrial_conference/

# scope: enumerate engines with civil hardcoded prompts (cross-check spike claim about 17 engines)
find engines/ -name "*.py" -path "*/prompts/*" | head -50
```

The 6.0a deliverable is `docs/plans/2026-04-07-layer-4-batch-6.0a-coupling-audit.md` (per plan v2 batch table). Plan to spend ~3-5 days on it; do not start writing code in 6.0a.

---

## 5. Environment state memo

**Worktree pollution**: there are 40+ worktrees accumulated across previous Layer 1-3 batches. `start_code_task` is hitting frequent timeouts because git operations on `.claude/worktrees/` traverse all of them. **First action when resuming**: prune.

```bash
cd C:/Users/david/dev/case-adversarial-engine
git worktree list   # inspect first
git worktree prune  # remove stale ones
# then manually remove fully-merged old branches:
git branch --merged main | grep -v 'main\|claude/epic-williamson' | xargs -r git branch -d
```

Be conservative — only remove worktrees whose branches are fully merged into main and where you're confident there's no in-progress work. The `claude/epic-williamson` worktree should be kept (it's where this handoff lives).

**CI status**:
- Last known green run: `24069720593` (covers commit `50f28fe`).
- Commit `4bdefda` is docs-only — should be green by inspection (no test changes).
- Commits `e03e92d` (spike report) and this handoff commit are docs-only — same.
- Worth a 30-second look at GitHub Actions when resuming, but no expected failures.

**Main HEAD**: `e03e92d` after the spike commit. After this handoff commit lands it'll be a new SHA — see Step 9 final report.

**pytest baseline**: **2,408 tests passing** as of Batch 5 landing. Layer 4 will add ~100 unit/E2E tests + 6-12 golden cases (per plan v2 §"问题 6"), targeting ~2,520+ tests at Layer 4 completion.

---

## 6. Open technical questions (the things plan v2 + spike did NOT answer)

These are the questions the next session should keep on its mental backlog:

1. **Does the inheritance verdict generalize beyond `issue_impact_ranker`?** Spike validated only one engine. Plan §"问题 5" warns that engines like `case_extractor`, `defense_chain`, and `pretrial_conference/judge` may degenerate (their existing prompts already have civil hardcoding). **Recommendation**: rerun spike methodology against `case_extractor` as a 6.1.0c mini-spike, ~30 min, before committing to full 17-engine rollout in 6.1.2.

2. **6.0b family-neutralization actual depth.** Plan v2 §"Reality Check" identifies this as the dominant remaining timeline risk. Cannot be answered until 6.0a audit deliverable is in hand. The Pessimistic 28+ wk scenario is entirely driven by this.

3. **Vocab research has not started.** Plan v2 §"问题 1" picks intentional_injury / theft / fraud (criminal) and 行政处罚 / 政府信息公开 / 工伤认定 (admin) as MVP subtypes. Per-subtype legal-vocabulary notes (anchored to specific 司法解释) need to be written and reviewed by a legal expert. **No vocab note exists yet for any of the 6 subtypes.** This is on the critical path for 6.1.3 (intentional_injury few-shot) and is the bottleneck plan v1 originally identified.

4. **Eval harness for criminal cases not designed.** The civil eval harness uses specific contract-shaped fixtures. Criminal cases need new fixture shape (case file, charge sheet, evidence in 卷宗 form). Plan v2 doesn't address this — it's currently absorbed into 6.1.4 "smoke test + golden case" but that line item is under-specified.

5. **Few-shot file count and reuse.** Plan v2 §"Few-shot 文件" estimates 6+ new few-shot files for `issue_impact_ranker` alone. The spike measured prompt reuse but not few-shot reuse. Few-shot files may not benefit from inheritance the same way prompts do. Worth a follow-up spike before 6.2 starts.

---

## 7. Key files cheat sheet (for fast cold-start)

| Path | Why it matters |
|---|---|
| `docs/plans/2026-04-07-layer-4-criminal-admin-plan.md` | Plan v2 — strategy source of truth. |
| `docs/plans/2026-04-07-layer-4-spike-6.1.0-report.md` | Spike result — read first when resuming. |
| `docs/plans/2026-04-07-layer-4-criminal-admin-plan.review.md` | Codex review of plan v1 — risk register reference. |
| `engines/simulation_run/issue_impact_ranker/prompts/labor_dispute.py` | Phase C.5b template exemplar for criminal base. |
| `engines/simulation_run/issue_impact_ranker/prompts/real_estate.py` | Same — Phase C.5b template exemplar. |
| `engines/simulation_run/issue_impact_ranker/prompts/civil_loan.py` | Outlier; needs 6.1.0b alignment cleanup before criminal base copies from civil. |
| `engines/shared/models/` | Coupling audit (6.0a) primary target — civil-shaped models live here. |
| `engines/simulation_run/case_type_plugin.py` (or wherever `CaseTypePlugin` Protocol lives) | Phase C.5a Plugin protocol; Layer 4 will extend this. |
| `engines/shared/few_shot_examples.py` | Few-shot loader — used by `load_few_shot_text(...)` in all per-case prompts. |
| `engines/simulation_run/procedure_setup/` | High-risk neutralization target (plan v2 C3 risk). |
| `engines/simulation_run/pretrial_conference/prompts/judge.py:41` | Cited by plan v2 line 332 as a hardcoded-civil example; check during 6.0a. |

---

## 8. Cold-start prompt (paste this into the next conversation)

```
我之前做到 Layer 4 spike 6.1.0 阶段。Layer 3 全部 ship 到 main 了
（Batch 1-5 + Batch 4 follow-up），Layer 4 plan v2 + codex review +
6.1.0 prompt-inheritance spike 都已经完成并 commit 到 main。

Spike verdict: OK with one tweak — 两层继承策略成立（civil 基线 reuse
75-84%，criminal 首子类型 75.4% 且 override 是纯加法结构）。下一步
应该直接开 Batch 6.0a coupling audit，但开工前需要把 spike 结果折回
plan v2（in-place edit，不写 v3）。

请先读 docs/plans/2026-04-07-layer-4-HANDOFF.md（200-400 行）拿到
完整上下文，然后按其中 §4 "Next-step instructions" 操作。第一件事
是清理 .claude/worktrees/ 下的 40+ 旧 worktree（start_code_task 一直
在超时），然后再开 6.0a。

main 当前 HEAD：<git log -1 --format=%H main 拿到的 SHA>
我现在所在 worktree：claude/epic-williamson（fast-forward 同步于 main）
```

---

## 9. One-line summary (the thing that matters most)

**Spike cleared the inheritance gate. Next click is Batch 6.0a coupling audit; first do a worktree prune and a 30-min in-place plan v2 edit to fold the spike result in. No plan v3 needed.**
