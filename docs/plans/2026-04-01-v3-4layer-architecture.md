# V3 四层报告架构设计 / V3 4-Layer Report Architecture

**Date**: 2026-04-01
**Status**: Implementation In Progress
**Supersedes**: v2 report generation in `_write_md()`

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Cover Summary (封面摘要层)              │ ← Decision-maker page
│  - Neutral conclusion                            │
│  - Perspective-driven summary (--perspective)     │
│  - Conditional scenario tree summary             │
│  - Evidence risk traffic light                   │
├─────────────────────────────────────────────────┤
│  Layer 2: Neutral Adversarial Core (中立对抗内核) │ ← Always neutral
│  2.1 Fact Base (事实底座)                         │
│  2.2 Issue Map (争点地图)                         │
│  2.3 Evidence Battle Matrix (证据作战矩阵)        │
│  2.4 Conditional Scenario Tree (条件场景树)        │
├─────────────────────────────────────────────────┤
│  Layer 3: Role-based Output (角色化输出层)         │ ← --perspective drives
│  plaintiff: claims, attack chains, supplements   │
│  defendant: defenses, challenges, motions        │
│  neutral (default): both sides equally           │
├─────────────────────────────────────────────────┤
│  Layer 4: Appendix (附录层)                       │ ← Always same
│  - 3-round adversarial transcripts               │
│  - Evidence index                                │
│  - Timeline                                      │
│  - Glossary                                      │
│  - Amount calculations                           │
└─────────────────────────────────────────────────┘
```

## Design Principles

1. **Neutral core ≠ perspective output**: Layers 1-2 are perspective-independent (except Layer 1B which adds a perspective summary ON TOP of neutral content)
2. **Facts/inferences/recommendations NEVER mixed**: Every section tagged with 「事实」「推断」「假设」「观点」「建议」
3. **No pseudo-precise probabilities**: Replace percentage estimates with conditional scenario trees (binary condition nodes: yes/no → next node)
4. **Evidence colors = stability only**: 🟢 third-party verifiable, 🟡 screenshots/single-party, 🔴 disputed+sensitive
5. **Card + table + tree format**: No long narrative paragraphs; each issue fits one screen with fixed fields

## Tag System

Every paragraph/section MUST carry one of:
- 「事实」 — Undisputed objective facts only
- 「推断」 — Logical inference from facts
- 「假设」 — Conditional assumption
- 「观点」 — Analytical opinion
- 「建议」 — Actionable recommendation

## Implementation Phases

### Phase 1: Data Models + Conditional Scenario Tree Engine (5 files max)
- `engines/report_generation/v3/models.py` — New 4-layer data models
- `engines/report_generation/v3/scenario_tree.py` — Conditional binary scenario tree builder (replaces probability-based DecisionPathTree in report display)
- `engines/report_generation/v3/tag_system.py` — Statement class tag enforcement
- `engines/report_generation/v3/__init__.py` — Package init
- `engines/report_generation/v3/evidence_classifier.py` — Evidence risk traffic light classifier (green/yellow/red)

### Phase 2: Evidence Battle Matrix Generator (5 files max)
- `engines/report_generation/v3/evidence_battle_matrix.py` — 7-question matrix per evidence
- `engines/report_generation/v3/issue_map.py` — Fixed-template issue map generator
- `engines/report_generation/v3/fact_base.py` — Undisputed fact extractor

### Phase 3: 4-Layer Report Writer (5 files max)
- `engines/report_generation/v3/report_writer.py` — Main 4-layer Markdown report generator (replaces `_write_md()`)
- `engines/report_generation/v3/layer1_cover.py` — Cover summary layer
- `engines/report_generation/v3/layer2_core.py` — Neutral adversarial core layer
- `engines/report_generation/v3/layer3_perspective.py` — Role-based output layer
- `engines/report_generation/v3/layer4_appendix.py` — Appendix layer

### Phase 4: CLI Integration + Tests (5 files max)
- `scripts/run_case.py` — Add `--perspective` flag, replace `_write_md()` call
- `engines/report_generation/v3/tests/test_models.py` — Model tests
- `engines/report_generation/v3/tests/test_report_writer.py` — Integration tests
- `engines/report_generation/v3/tests/test_evidence_battle_matrix.py` — Matrix tests
- `engines/report_generation/v3/tests/test_scenario_tree.py` — Scenario tree tests

## Layer Details

### Layer 1: Cover Summary

```markdown
# 案件诊断报告
## A. 中立结论摘要 「事实」
> One-sentence neutral conclusion about the case

## B. {perspective} 视角摘要 「建议」
### plaintiff:
- 三大优势
- 两大危险
- 三项立即行动

### defendant:
- 三大防线
- 原告可能补强方向
- 最优攻击顺序

## C. 条件场景树摘要 「推断」
if-then format, NO percentages

## D. 证据风险红绿灯 「事实」
🟢 第三方可核实 | 🟡 截图/单方 | 🔴 争议+敏感
```

### Layer 2.3: Evidence Battle Matrix

Per evidence piece, 7 fixed questions:
1. 这是什么证据 (What is this evidence)
2. 证明什么命题 (Which proposition does it prove)
3. 证明方向 (Proof direction)
4. 真实性/完整性/关联性/合法性风险 (Authenticity/completeness/relevance/admissibility risks)
5. 对方如何攻击 (How will opponent attack)
6. 如何加固 (How to reinforce)
7. 若此证据失败，哪些结论需重新计算 (If fails, which conclusions need recalculation)

### Layer 2.4: Conditional Scenario Tree

Binary condition nodes replacing probability estimates:
```
录音是否被采信？
├── 是 → 借款合意是否成立？
│   ├── 是 → 原告胜诉（全额或部分）
│   └── 否 → 进入代收款抗辩审查
└── 否 → 书面证据是否充分？
    ├── 是 → ...
    └── 否 → ...
```

### Layer 3: Perspective-Driven Output

When `--perspective plaintiff`:
- 三大诉请 + 证据支撑
- 被告攻击链预警
- 需补强证据清单
- 庭审举证顺序建议
- 应放弃的诉请

When `--perspective defendant`:
- 三大防线 + 证据支撑
- 原告可能补强方向
- 优先质证目标
- 应提交的动议
- 过度主张警告

When no `--perspective` (default):
- Both sides displayed equally

## CLI Changes

```bash
# New flag
python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml --perspective plaintiff
python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml --perspective defendant
python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml  # default: both sides
```
