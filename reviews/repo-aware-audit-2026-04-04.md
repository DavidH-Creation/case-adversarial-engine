# Repo-Aware Audit

Date: 2026-04-04  
Reference state: `main` at `9011c4a`

## Opening Judgment

**事实**：`acceptance contract` 与主线 `semantics` 的错位已经被实质修复，`render contract` 也已经进入主线代码和测试。  
**推断**：repo 已经从“方向对但未 enforce”进入“核心 contract 开始 enforce”的阶段。  
**保留意见**：当前还不能说“输出层已经 clean 了”，只能说“格式 clean gate 已有”；真正的 user-facing quality 仍明显不足，同时 public API 仍存在 `case_id` / `run_id` contract 漂移。

核心证据锚点：

- acceptance 对齐：`scripts/run_acceptance.py`
- render gate：`engines/report_generation/v3/report_writer.py`、`engines/report_generation/v3/tests/test_render_contract.py`
- API contract drift：`api/app.py`

## Confirmed Progress

这次可以确认的实质进步有三点：

1. **主线 contract 分叉问题已基本压住。**  
   `scripts/run_acceptance.py` 现在用 ordered top-k issue sequence 来衡量 `consistency`，`path_explainable` 也已切换到当前主线 artifacts 语义，不再把 `mediation_path` 当作主线必需项。这个问题不能再被描述为“acceptance gate 仍然落在旧世界里”。

2. **render gate 已经上线并被测试 enforce。**  
   `write_v3_report_md()` 现在会 humanize，再做 render lint，`test_render_contract.py` 还把 checked-in sample report 也纳入了门禁。这个问题不能再被描述为“render 代码比 render 证据更先进，当前 repo 还没有 contract 兑现机制”。

3. **repo-aware 的评审重心已经变化。**  
   现在最有价值的批评点，不再是 ontology 是否存在、acceptance 是否还守旧语义、或 raw ID 泄漏是否无人处理；现在真正重要的是：`user-clean quality`、public API ID 语义、DOCX 同强度门禁，以及真实多案型行为验收。

## Current High-Priority Gaps

### 1. Render 已达到 format-clean，但仍未达到 user-clean

当前主线已经具备 `format-clean` 门禁：

- 不允许 internal IDs
- 不允许空 level-2 section
- 不允许 placeholder-only table

但这不等于 `user-clean`。checked-in sample report 虽然已通过 render contract，仍然存在明显的产品质量缺口：

- 出现连续 `????????` 这类垃圾串
- fallback 文案占比很高
- 报告更像 lint-pass 的 baseline artifact，而不像可给律师看的文档

所以更准确的判断是：

> 主线已经有 `format-clean gate`，但 sample output 仍不是 `user-clean output`。

### 2. Public ID contract 仍有具体且危险的漂移

`GET /api/cases/{case_id}/artifacts` 当前返回的是：

```json
{"run_id": case_id, "artifacts": ...}
```

而同一文件中其他接口对外又在使用真实的 `record.run_id`。这不是命名小问题，而是 public API 语义漂移：

- 内部已经开始认真区分 `case / run / scenario`
- 对外接口至少有一处仍把 `case_id` 冒充成 `run_id`

这会直接影响前端、artifact consumer、scenario workflow 的兼容性和后续迁移成本。

### 3. DOCX 不是“完全没管”，但还没有和 Markdown 同强度的 render-clean gate

当前更准确的表述应该是：

- DOCX 已有 smoke / probability-free / parity 相关测试
- 但还没有和 Markdown 同强度的 render-clean gate

因此不能说 “DOCX 还没管”，也不能说 “DOCX 已经同等 enforce”。最准确的判断是：

> DOCX 已有基础质量保护，但还没有纳入与 Markdown 等价的 user-visible cleanliness gate。

### 4. 真实多案型 behavior acceptance 仍然是最硬的未证实点之一

当前 repo 已经具备：

- 多案型 fixtures
- 多案型 harness-level acceptance
- 明确的 mock-based structure validation

但当前 repo 还不具备足够强的真实模型行为级验收。因此：

- “repo 支持多案型”成立
- “civil kernel 的真实泛化能力已被稳健证明”还不成立

这条依然应该保留，而且优先级很高。

## Top 3 Next Steps

### 1. 把 render gate 从 `format-clean` 升级到 `user-clean`

当前下一步不该继续只盯 internal token，而应该把用户可感知质量也纳入门禁：

- 禁止连续 `?` / 垃圾串 / 明显编码异常进入用户可见输出
- 统计 fallback ratio，超过阈值直接 fail
- 检查 major section completeness，避免“有标题但几乎全是 fallback”
- 把 checked-in sample report 从 “lint-clean baseline” 升级成 “可阅读 baseline”

如果继续只守 `format-clean`，你得到的仍可能是“干净但空壳”的文档。

### 2. 修补 `case_id / run_id / scenario_id` 的 public contract

要做一轮外部接口审计，统一以下语义：

- 哪些字段永远是 `case` 维度
- 哪些字段永远是 `run` 维度
- 哪些字段永远是 `scenario` 维度

优先检查：

- artifacts endpoint
- analysis payload
- scenario baseline references
- workspace recovery exposed fields

这一步的目标不是重构内部模型，而是堵住 public API contract drift。

### 3. 做真实多案型 behavior acceptance

至少选：

- 1 个 `civil_loan`
- 1 个 `labor_dispute`
- 1 个 `real_estate`

用真实模型运行或稳定 recorded artifacts 做行为级验收，并记录：

- issue-tree stability
- citation completeness
- render cleanliness
- fallback ratio

这样才能真正回答 civil kernel 是否已经具有跨案型泛化能力，而不是只在 mock harness 里成立。

## Closing Thesis

主线 contract 分叉问题已经基本被压住；当前第一优先级不再是 gate 语义，而是把 render-clean 提升成 user-clean，同时修补仍然存在的 public ID contract 漂移，并用真实多案型行为验收证明 civil kernel 的泛化能力。
