# v3 实施计划：Output Track — 报告质量与导出一致性

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

日期：2026-04-06
修订：2026-04-06（adversarial review 后修订）

## 概览

v3 是 **Output Track**，与 Core Track (v2/v2.5) 分开演进。目标是将报告系统从"能跑通"提升到"律师可直接交付客户"的品质：

- **Markdown 报告质量**：从 format-clean 升级到 user-clean（消除 fallback 垃圾、JSON 泄露、section 空壳）
- **DOCX 完整集成**：v3 四层报告架构驱动 DOCX 生成，与 Markdown 语义对齐
- **Render contract 执行**：所有 10 条规则在 pipeline 中作为硬门禁
- **多案型报告验证**：civil_loan / labor_dispute / real_estate 三种案型的报告质量达标
- **报告恢复与幂等**：`--resume` 从��久化产物重新生���报告，结果一致

### 当前基线（v3.2 on main）

| 已有 | 状态 | 对抗审查备注 |
|------|------|-------------|
| 四层报告架构（cover/core/perspective/appendix） | ✅ 完整 | models.py 含 V3.1 双层证据卡 + SectionTag |
| Markdown report_writer.py | ✅ 能生成完整 MD | lint gate 已硬化——ERROR 级别已抛 RenderContractViolation |
| render_contract.py（10 条规则） | ✅ 规则定义完整，**ERROR 级别已阻断** | lint 在 report_writer 末尾调用，WARN 结果未记录到日志 |
| docx_generator.py 中 `generate_docx_v3_report()` | ⚠️ 函数已存在但**未接入 pipeline** | scripts/run_case.py 和 api/service.py 仍调用旧 `generate_docx_report()` |
| fallback ratio gate（>0.35 抛异常，0.20-0.35 WARN） | ✅ 已实现，阈值偏松（目标 >0.20 FAIL） | render_contract.py 两处阈值需修改 |
| 多案型 pipeline | ✅ 能跑但报告质量未验证 | 3 种案型 prompt 模块已注册 |
| CheckpointManager | ✅ 已实现，**但不跟踪 v3 产物** | 仅存 result_json + report_md，缺 report_v3.json 和 v3 docx |

### 关键缺口

1. **报告内容质量**：LLM 生成的文本大量使用 fallback 模板、section 内容过短、证据引用不完整
2. **DOCX 与 MD 脱节**：pipeline 仍调用旧 `generate_docx_report()`，`generate_docx_v3_report()` 虽已实现但未接入；且 Layer2 渲染缺 evidence_cards 和 unified_electronic_strategy
3. **WARN 级别不可见**：render contract WARN 结果未写入日志，运维无法监控报告质量趋势
4. **多案型报告未验收**：没有 golden reference 对比
5. **恢复路径未测试**：`--resume` 生成的报告与首次生成是否一致；checkpoint 不区分 v2/v3 产物
6. **无自动修复器**：lint 捕获的 CJK 标点、重复标题、表格列数等问题只能 FAIL，不能自动修复后重试

---

## 分阶段交付

### Phase 1：ReportFixer + 阈值收紧 + WARN 日志

**目标**：构建自动修复器，收紧 fallback ratio 阈值到 0.20，补全 WARN 日志输出。

> **基线确认**：lint gate 的 ERROR→raise 机制**已在 report_writer.py 中工作**（`lint_markdown_render_contract()` 在 ERROR 时抛 `RenderContractViolation`）。本阶段无需重新实现 lint gate，聚焦于修复器、阈值和日志。

#### 1.1 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `engines/report_generation/v3/render_contract.py` | 收紧 fallback ratio 阈值：0.35→0.20 FAIL，0.10→0.20 改为 0.10-0.20 WARN |
| 修改 | `engines/report_generation/v3/report_writer.py` | 在 lint 前插入 ReportFixer.apply_all()；lint 后捕获 WARN 写入 logger.warning |
| 新建 | `engines/report_generation/v3/report_fixer.py` | 自��修复器：CJK 标点、重复标题去重、表格列数补齐 |
| 新建 | `engines/report_generation/v3/tests/test_report_fixer.py` | 修复器单元测试 |
| 修改 | `engines/report_generation/v3/tests/test_render_contract.py` | 补充阈值边界测试（0.19→PASS, 0.20→PASS, 0.21→FAIL） |

#### 1.2 ReportFixer 设计

```python
# engines/report_generation/v3/report_fixer.py

class ReportFixer:
    """在 lint 之前自动修复可修复的问题。不做语义修改，仅做格式修正。"""

    def fix_cjk_punctuation(self, md: str) -> str:
        """CJK 文本后的 ASCII 标点 → 全角标点（逗号、句号、冒号、分号）"""
        ...

    def fix_duplicate_headings(self, md: str) -> str:
        """重复的 ## 标题添加序号后缀（如 ## 证据分析 → ## 证据分析 (2)）"""
        ...

    def fix_table_column_mismatch(self, md: str) -> str:
        """表格行列数不匹配时：列少补空 cell，列多截断"""
        ...

    def apply_all(self, md: str) -> tuple[str, list[str]]:
        """依次应用所有修复。返回 (fixed_md, applied_fixes_log)。"""
        ...
```

#### 1.3 report_writer.py 集成变更

```python
# 在 write_v3_report_md() 中，lint 调用之前：
from .report_fixer import ReportFixer

fixer = ReportFixer()
content, fix_log = fixer.apply_all(content)
for entry in fix_log:
    _logger.info("report-fixer: %s", entry)

# lint 调用之后，捕获并记录 WARN（当前 WARN 被静默丢弃）：
results = lint_markdown_render_contract(content, evidence_ids=evidence_id_set)
warnings = [r for r in results if r.severity == LintSeverity.WARN]
for w in warnings:
    _logger.warning("render-contract WARN [%s]: %s", w.rule, w.message)
# ERROR 级别已由 lint_markdown_render_contract 内部 raise
```

Pipeline 流程变为：**LLM 生成 → ReportFixer.apply_all() → lint（WARN 记日志，ERROR raise） → gate**

#### 1.4 Fallback Ratio 阈值收紧

当前实现（render_contract.py）：
- ≤0.20 PASS（静默）
- 0.20-0.35 WARN（但 WARN 未记录，等于静默）
- \>0.35 FAIL（raise RenderContractViolation）

目标：
- ≤0.10 PASS
- 0.10-0.20 WARN（记日志）
- \>0.20 FAIL（raise）

**过渡策略**：先改为 >0.25 FAIL，Phase 3 多案型验收后再收到 0.20。避免一步到位导致现有 pipeline 全面失败。

#### 1.5 实施步骤

- [ ] Step 1：写 ReportFixer 失败测试（CJK 标点、重复标题、表格列数各 2-3 个用例）
- [ ] Step 2：实现 ReportFixer（apply_all 返回 fix_log）
- [ ] Step 3：在 report_writer.py 中插入 fixer（lint 前）+ WARN 日志（lint 后）
- [ ] Step 4：修改 render_contract.py 阈值：0.35→0.25（过渡阶段）
- [ ] Step 5：补充 test_render_contract.py 的阈值边界测试
- [ ] Step 6：全量测试 + 提交

#### 1.6 验收标准

- [ ] ReportFixer 能自动修复 CJK 标点、重复标题、表格列数不匹配
- [ ] apply_all() 返回 fix_log 记录每次修复操作
- [ ] WARN 级别 lint 结果写入 logger.warning（可 grep 日志）
- [ ] fallback ratio >0.25 阻断 pipeline（过渡阶段）
- [ ] 全量测试通过

#### 1.7 工作量估计

~1.5-2 天。ReportFixer 是纯字符串处理，阈值修改是常量替换，WARN 日志是 3 行代码。

---

### Phase 2：DOCX v3 Pipeline 接入 + 渲染补全

**目标**：将 pipeline 切换到调用已有的 `generate_docx_v3_report()`，并补全 Layer2/Layer4 渲染缺口。

> **基线确认**：`generate_docx_v3_report()` 已实现在 `docx_generator.py`（~line 1056），含 Layer1-4 基本渲染。但 Layer2 缺 evidence_cards（双层证据卡）和 unified_electronic_strategy；且 scripts/run_case.py 仍调用旧 `generate_docx_report()`。

#### 2.1 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `engines/report_generation/docx_generator.py` | 补全 `_render_v3_layer2()` 的 evidence_cards 和 unified_electronic_strategy 渲染；补全 `_render_v3_layer4()` glossary 细节；提取样式常量 |
| ��建 | `engines/report_generation/v3/docx_styles.py` | DOCX 样式常量（CLR_*, SZ_*, FONT_*）从 docx_generator.py 提取 |
| 新建 | `engines/report_generation/v3/docx_lint.py` | DOCX render contract lint（提取文本后复用 MD 规则子集） |
| 修改 | `scripts/run_case.py` | DOCX 生成从 `generate_docx_report()` 切换到 `generate_docx_v3_report(report_v3=...)` |
| 修改 | `api/service.py` | API DOCX 生成走 v3 路径（需先在 run_analysis 中构建 FourLayerReport） |
| 修改 | `engines/report_generation/docx_generator.py` 旧函数 | `generate_docx_report()` 内部转发到 v3 路径（向后兼容） |
| 新建 | `engines/report_generation/v3/tests/test_docx_v3.py` | DOCX v3 渲染测试 |

#### 2.2 实际工作分解

**已有（无需重写）**：
- `generate_docx_v3_report()` 函数入口
- Layer1 Cover 渲染（含 V3.1 winning_move/blocking_conditions fallback）
- Layer3 Perspective 渲染
- 基础样式系统

**需要补全**：
- Layer2 `_render_v3_layer2()`：添加 evidence_cards 双层卡片渲染（EvidenceBasicCard 4 字段 / EvidenceKeyCard 6 字段）
- Layer2：添加 unified_electronic_strategy section
- Layer4 `_render_v3_layer4()`：补全 glossary_md 渲染、amount_calculation_md 渲染
- Timeline 表格：humanize evidence source IDs（当前直接输出 `src-xxx`）

**Pipeline 路由修复（关键）**：
```python
# scripts/run_case.py — 当前（错误）：
docx_path = generate_docx_report(out, issue_tree, ...)  # v2 路径

# 修改为：
from engines.report_generation.docx_generator import generate_docx_v3_report
v3_data = json.loads(v3_json_path.read_text())  # report_v3.json 已在前一步保存
docx_path = generate_docx_v3_report(out, report_v3=v3_data, similar_cases=...)
```

#### 2.3 DOCX Render Contract

```python
# engines/report_generation/v3/docx_lint.py

def lint_docx_render_contract(doc_path: Path) -> list[LintResult]:
    """从生成的 DOCX 提取文本后跑 render contract 子集。"""
    doc = Document(str(doc_path))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    # 复用 MD 的规则子集：forbidden_tokens, raw_json_leak, duplicate_heading
    ...
```

#### 2.4 实施步骤

- [ ] Step 1：提取样式常量到 docx_styles.py（纯重构，不改行为）
- [ ] Step 2：写 DOCX v3 渲染测试（FourLayerReport mock → DOCX → 验证 section 存在性）
- [ ] Step 3：补全 `_render_v3_layer2()` — evidence_cards 双层表格 + unified_electronic_strategy
- [ ] Step 4：补全 `_render_v3_layer4()` — glossary + amount_calculation
- [ ] Step 5：humanize timeline source IDs（src-xxx → 人类可读标签）
- [ ] Step 6：实现 docx_lint.py（DOCX render contract）
- [ ] Step 7：修改 scripts/run_case.py — 切换到 `generate_docx_v3_report()`
- [ ] Step 8：修改 api/service.py — 构建 FourLayerReport + 调用 v3 DOCX 路���
- [ ] Step 9：��� `generate_docx_report()` 内部转发到 v3（向后兼容 shim）
- [ ] Step 10：跑 civil_loan pipeline，验证 MD 和 DOCX section 标题对齐
- [ ] Step 11：全量测试 + 提交

#### 2.5 验收标准

- [ ] Pipeline（scripts/run_case.py + api/service.py）调用 `generate_docx_v3_report()`
- [ ] DOCX Layer2 包含 evidence_cards 双层表格 + unified_electronic_strategy section
- [ ] DOCX 和 MD 的 section 标题、内容结构完全对应
- [ ] DOCX 通过 render contract 子集（forbidden_tokens, raw_json_leak, duplicate_heading）
- [ ] CJK 字体 fallback 正确（SimSun/Microsoft YaHei）
- [ ] pipeline 生成的 DOCX 能被 Word/LibreOffice 正常打开
- [ ] 旧 `generate_docx_report()` 的 public API 保持向后兼容（内部转发）

#### 2.6 工作量估计

~2.5-3.5 天。函数入口已存在，主要工作是 Layer2 evidence_cards 双层表格渲染 + pipeline 路由 + DOCX lint。

---

### Phase 3：多案型报告验收

**目标**：civil_loan / labor_dispute / real_estate 三种案型的报告全部通过 render contract + 内容完整性检查。

#### 3.1 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `outputs/acceptance/v3/` | v3 报告 golden artifacts（MD + DOCX per case type） |
| 新建 | `engines/report_generation/v3/tests/test_multi_case_type_reports.py` | 多案型报告集成测试 |
| 修改 | `engines/report_generation/prompts/civil_loan.py` | 优化 prompt 减少 fallback |
| ���改 | `engines/report_generation/prompts/labor_dispute.py` | 优化 prompt 减少 fallback |
| 修改 | `engines/report_generation/prompts/real_estate.py` | 优化 prompt 减少 fallback |
| 修改 | `engines/report_generation/v3/layer2_core.py` | 案型特化的 section 模板 |
| 修改 | `engines/report_generation/v3/layer3_perspective.py` | 案型特化的视角分析 |
| 修改 | `engines/report_generation/v3/render_contract.py` | 最终阈值收紧：0.25→0.20 FAIL |

#### 3.2 验收矩阵

| 检查项 | civil_loan | labor_dispute | real_estate |
|--------|-----------|---------------|-------------|
| MD render contract 10/10 通过 | | | |
| DOCX render contract 通过 | | | |
| fallback ratio ≤ 0.20 | | | |
| 所有 major section 有实质内容（≥50字） | | | |
| 证据引用无 orphan citation | | | |
| 金额计算 section 正确处理（有/无） | | | |
| 执行摘要非 boilerplate | | | |
| Layer3 三视角（原告/被告/中立）均有实质内容 | | | |

#### 3.3 实施步骤

- [ ] Step 1：跑 civil_loan pipeline，记录 lint 结果（MD + DOCX）
- [ ] Step 2：修复 civil_loan 的 lint 违规（prompt 优化 + fixer）
- [ ] Step 3：跑 labor_dispute pipeline，记录 lint 结果
- [ ] Step 4：修复 labor_dispute 特有问题（amount_calculation_report=None 路径、劳动争议特化 prompt）
- [ ] Step 5���跑 real_estate pipeline，记录 lint 结果
- [ ] Step 6：修复 real_estate ���有问题（物权/合同双重法律关系的 section 结构）
- [ ] Step 7：最终阈值收紧：fallback ratio 0.25→0.20
- [ ] Step 8：三种案型的最终报告存为 golden artifacts
- [ ] Step 9：写集成测试对比 golden artifacts 的结构（section 数量、标题列表、证据引用完整性）
- [ ] Step 10：全量测试 + ���交

#### 3.4 验收标准

- [ ] 三种案型的 MD 和 DOCX 报告全部通过 render contract
- [ ] fallback ratio 均 ≤ 0.20（最终阈值）
- [ ] amount_calculation_report=None 的案型（labor_dispute, real_estate）不报错、不出空 section
- [ ] golden artifacts 存入 outputs/acceptance/v3/
- [ ] 集成测试验证报告结构（section 数量、标题列表、证据引用完整性）

#### 3.5 工作��估计

~5-7 天。每种案型需要完整 pipeline run（~25-30分钟），加上 prompt 调优迭代。prompt 调优通常需要 2-3 轮才能稳定在 fallback ratio ≤ 0.20。

---

### Phase 4：报告恢复与幂等

**目标**：`--resume` 从持久化产物重新生成报告，结果与首次生成结构一致（幂等性）。

> **基线确认**：`CheckpointManager` 已实现且在 scripts/run_case.py 中使用，但仅保存 `result_json` + `report_md`，**不保存 `report_v3.json` 和 v3 DOCX 路径**。resume 逻辑无法区分 v2/v3 产物。

#### 4.1 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `scripts/run_case.py` | checkpoint 增存 report_v3.json + v3 docx 路径；`--resume` 路径走 v3 report_writer |
| 修改 | `engines/report_generation/v3/report_writer.py` | 新增 `rebuild_from_artifacts()` 方法 |
| 修改 | `engines/shared/checkpoint.py` | CheckpointState 增加 v3 产物字段（向后兼容旧 checkpoint） |
| 新建 | `engines/report_generation/v3/tests/test_resume_rebuild.py` | 恢复一致性测试 |

#### 4.2 设计

```python
# report_writer.py 新增
def rebuild_from_artifacts(
    workspace_dir: Path,
    case_id: str,
) -> tuple[str, Path]:
    """从磁盘产物重建 FourLayerReport → 重新生成 MD + DOCX。
    不调用 LLM，仅读取持久化数据。
    返回 (markdown_content, docx_path)。

    步骤：
    1. 读取 report_v3.json → 反序列化为 FourLayerReport
    2. 调用 write_v3_report_md()（含 fixer + lint gate）
    3. 调用 generate_docx_v3_report()
    4. 返回结果
    """
    ...
```

```python
# scripts/run_case.py checkpoint 变更
# 保存时增加 v3 产物：
ckpt.save(STEP_OUTPUTS, {
    "result_json": str(jp),
    "report_md": str(mp),
    "report_v3_json": str(v3_json_path),   # 新增
    "report_v3_docx": str(v3_docx_path),   # 新增
})

# 恢复时区分 v2/v3：
artifacts = ckpt.load()
if "report_v3_json" in artifacts:
    md, docx = rebuild_from_artifacts(workspace_dir, case_id)
else:
    # 旧 v2 checkpoint，走旧路径
    ...
```

幂等性定义：首次生成和 resume 生成的报告在**结构**上一致（section 标题和顺序相同），**内容**可能因时间戳等微调而有差异，但 render contract 结果相同。

#### 4.3 实施步骤

- [ ] Step 1：写恢复一致性失败测试（mock 产物目录 → rebuild → 对比结构）
- [ ] Step 2：实现 rebuild_from_artifacts()（反序列化 + 重渲染，零 LLM 调用）
- [ ] Step 3：修改 CheckpointState 增加 v3 产物字段（向后兼容）
- [ ] Step 4：修改 scripts/run_case.py checkpoint 保存逻辑
- [ ] Step 5：修改 scripts/run_case.py --resume 路径
- [ ] Step 6：跑一次完整 pipeline → resume → 对比 section 标题列表
- [ ] Step 7：全量测试 + 提交

#### 4.4 验收标准

- [ ] `rebuild_from_artifacts()` 不调用 LLM
- [ ] resume 生成的报告通过 render contract
- [ ] resume 和首次生成的 section 标题列表完全一致
- [ ] resume 生成的 DOCX 结构与首次一致
- [ ] 旧 checkpoint（不含 v3 字段）仍能正常恢复（向后兼容）

#### 4.5 工作量估计

~3-4 天。rebuild_from_artifacts 本身不复杂，但 checkpoint 向后兼容 + v2/v3 分支逻辑需要仔细测试。

---

## 整体依赖关系

```
Phase 1 (ReportFixer + 阈值 + WARN 日志)  ──→  必须先做
    │
    ├─► Phase 2 (DOCX v3 接入 + 渲染补全) ← 依赖 Phase 1 的 fixer 和 gate
    │       │
    │       └��► Phase 3 (多案型验收)       ← 依赖 Phase 1+2 的完整 pipeline
    │
    └─► Phase 4 (恢复与幂等)               ← 依赖 Phase 1 的 report_writer 变更
```

执行顺序：**Phase 1 → Phase 2 → Phase 3 → Phase 4**（严格顺序，每个 Phase 依赖前一个）

Phase 4 也可以和 Phase 3 并行（resume 逻辑独立于多案型验收），但建议 Phase 3 先做——golden artifacts 作为 Phase 4 的 rebuild 测试输入更可靠。

## 风险与缓解

| 风险 | 严重度 | 缓解 |
|------|--------|------|
| LLM 输出不稳定导致 fallback ratio 波动 | 高 | ReportFixer 自动修复 + prompt 模板固化 section 结构 |
| DOCX 渲染与 Word/LibreOffice 兼容性 | 中 | 用 python-docx 标准 API，避免直接操作 XML |
| 收紧阈值后现有 pipeline 大量失败 | 中 | 分步收紧：Phase 1 先 0.25，Phase 3 稳定后 0.20 |
| 多案型 pipeline run 耗时（每次 25-30 分钟） | 低 | 并行跑不同案型 |
| docx_generator.py 向后兼容 | 中 | 保留 public API，`generate_docx_report()` 内部转发到 v3 |
| checkpoint 向后兼容（旧 v2 vs 新 v3） | 中 | CheckpointState 新字段 Optional，加载时检测有无 v3 产物 |
| Layer2 evidence_cards 渲染复杂度 | 中 | 双层卡片（4 字段 / 6 字段）需要不同表格模板，逐层实现 |

## 总工作量估计

| Phase | 估计 | 备注 |
|-------|------|------|
| Phase 1 ReportFixer + 阈值 + WARN 日志 | 1.5-2 天 | lint gate 已工作，聚焦 fixer |
| Phase 2 DOCX v3 接入 + 渲染补全 | 2.5-3.5 天 | 函数入口已存在，聚焦 Layer2 补全 + pipeline 路由 |
| Phase 3 多案型报告验收 | 5-7 天 | prompt 调优迭代 + golden artifacts |
| Phase 4 报告恢复与幂等 | 3-4 天 | checkpoint 向后兼容 + rebuild |
| **合计** | **12-16.5 天** |  |

---

## 附录：对抗审查摘要（Adversarial Review）

> 以下是对本计划初始版本的对抗审查发现，已全部整合到上方各 Phase 中。

### Finding 1: 基线表描述与代码实际状态不符（HIGH）

**原计划声称** "Render contract 未阻断——lint 结果仅记录 warning，不阻断 pipeline"。

**实际**：`report_writer.py` 调用 `lint_markdown_render_contract()`，该函数在任何 ERROR 级别规则触发时已 `raise RenderContractViolation`。lint gate **已在工作**。

**影响**：Phase 1 若按原计划重新实现 lint gate，会产生冗余代码。已修正为聚焦 ReportFixer + 阈值 + WARN 日志。

### Finding 2: DOCX v3 函数已存在但 pipeline 未接入（HIGH）

**原计划声称** Phase 2 需"新建 docx_v3_generator.py"。

**实际**：`generate_docx_v3_report()` 已存在于 `docx_generator.py`（~line 1056），含 Layer1-4 基本渲染。但 `scripts/run_case.py` 和 `api/service.py` 仍调用旧 `generate_docx_report()`。

**影响**：Phase 2 从"从零构建"改为"补全渲染 + 切换路由"，工作量从 4-5 天降至 2.5-3.5 天。

### Finding 3: Layer2 DOCX 渲染不完整（MEDIUM）

`_render_v3_layer2()` 存在但缺少：
- evidence_cards（V3.1 双层证据卡系统：EvidenceBasicCard 4 字段 / EvidenceKeyCard 6 字段）
- unified_electronic_strategy section
- 仅渲染旧版 evidence_battle_matrix（7 题矩阵）

已纳入 Phase 2 Step 3-4。

### Finding 4: WARN 结果被静默丢弃（MEDIUM）

`lint_markdown_render_contract()` 返回包含 WARN 的 `list[LintResult]`，但 `report_writer.py` 仅依赖其 raise 行为（ERROR），WARN 被丢弃。运维无法监控报告质量退化趋势。

已纳入 Phase 1 Step 3。

### Finding 5: Checkpoint 不跟踪 v3 产物（MEDIUM）

`CheckpointManager.save()` 仅保存 `result_json` + `report_md`，不保存 `report_v3.json` 和 v3 DOCX 路径。resume 逻辑无法区分 v2/v3 产物，可能导致 resume 后生成 v2 DOCX 而非 v3。

已纳入 Phase 4 Step 3-5，增加向后兼容设计。

### Finding 6: Phase 4 工作量低估（LOW）

原计划估计 2-3 天，但 `rebuild_from_artifacts()` 需要：反序列化 FourLayerReport JSON → 调用 fixer + lint → 生成 MD + DOCX → checkpoint v2/v3 分支逻辑。加上向后兼容测试，实际需要 3-4 天。

### Finding 7: 阈值一步收紧风险（LOW）

原计划直接从 0.35→0.20。如果 LLM prompt 未同步优化，所有现有 pipeline 将立即失败。改为分步：Phase 1 先 0.25，Phase 3 验收通过后再 0.20。

---

*计划版本：v3-rev1（adversarial review 后修订） · 生成日期：2026-04-06*
