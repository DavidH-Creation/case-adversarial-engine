# v3 实施计划：Output Track — 报告质量与导出一致性

日期：2026-04-06

## 概览

v3 是 **Output Track**，与 Core Track (v2/v2.5) 分开演进。目标是将报告系统从"能跑通"提升到"律师可直接交付客户"的品质：

- **Markdown 报告质量**：从 format-clean 升级到 user-clean（消除 fallback 垃圾、JSON 泄露、section 空壳）
- **DOCX 完整集成**：v3 四层报告架构驱动 DOCX 生成，与 Markdown 语义对齐
- **Render contract 执行**：所有 10 条规则在 pipeline 中作为硬门禁
- **多案型报告验证**：civil_loan / labor_dispute / real_estate 三种案型的报告质量达标
- **报告恢复与幂等**：`--resume` 从持久化产物重新生成报告，结果一致

### 当前基线（v3.2 on main）

| 已有 | 状态 |
|------|------|
| 四层报告架构（cover/core/perspective/appendix） | ✅ 完整 |
| Markdown report_writer.py | ✅ 能生成完整 MD |
| render_contract.py（10 条规则） | ✅ 规则定义完整 |
| docx_generator.py | ⚠️ 旧版，未集成 v3 四层架构 |
| fallback ratio gate（>35% 抛异常） | ✅ 已实现但阈值可能偏松 |
| 多案型 pipeline | ✅ 能跑但报告质量未验证 |
| 报告 lint 在 pipeline 中执行 | ⚠️ 部分——仅在 report_writer 末尾 |

### 关键缺口

1. **报告内容质量**：LLM 生成的文本大量使用 fallback 模板、section 内容过短、证据引用不完整
2. **DOCX 与 MD 脱节**：docx_generator.py 直接从原始数据生成，不经过 v3 四层架构
3. **Render contract 未阻断**：lint 结果仅记录 warning，不阻断 pipeline
4. **多案型报告未验收**：没有 golden reference 对比
5. **恢复路径未测试**：`--resume` 生成的报告与首次生成是否一致

---

## 分阶段交付

### Phase 1：Render Contract 硬门禁 + Markdown 质量提升

**目标**：让 render contract 的 ERROR 规则真正阻断 pipeline，修复已知的 Markdown 质量问题。

#### 1.1 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `engines/report_generation/v3/render_contract.py` | 细化规则阈值，增加诊断信息 |
| 修改 | `engines/report_generation/v3/report_writer.py` | lint 失败时 ERROR 级别抛异常阻断 |
| 修改 | `scripts/run_case.py` | pipeline 末端集成 lint gate |
| 修改 | `api/service.py` | API pipeline 集成 lint gate |
| 新建 | `engines/report_generation/v3/report_fixer.py` | 自动修复器：CJK 标点、短 section 扩充、重复标题去重 |
| 新建 | `engines/report_generation/v3/tests/test_report_fixer.py` | 修复器测试 |
| 修改 | `engines/report_generation/v3/tests/test_render_contract.py` | 补充边界测试 |

#### 1.2 Lint Gate 集成设计

```python
# report_writer.py — 生成完成后
lint_results = lint_markdown_render_contract(markdown, evidence_ids=evidence_ids)
errors = [r for r in lint_results if r.severity == LintSeverity.ERROR]
warnings = [r for r in lint_results if r.severity == LintSeverity.WARN]

for w in warnings:
    _logger.warning("render-contract WARN: %s — %s", w.rule, w.message)

if errors:
    error_detail = "\n".join(f"  [{e.rule}] {e.message}" for e in errors)
    raise RenderContractViolation(
        f"报告未通过 render contract（{len(errors)} 个 ERROR）:\n{error_detail}"
    )
```

#### 1.3 Report Fixer 设计

```python
# engines/report_generation/v3/report_fixer.py

class ReportFixer:
    """在 lint 之前自动修复可修复的问题。"""

    def fix_cjk_punctuation(self, md: str) -> str:
        """CJK 文本后的 ASCII 标点 → 全角标点"""
        ...

    def fix_duplicate_headings(self, md: str) -> str:
        """重复的 ## 标题添加序号后缀"""
        ...

    def fix_table_column_mismatch(self, md: str) -> str:
        """表格行列数不匹配时补齐或截断"""
        ...

    def apply_all(self, md: str) -> str:
        """依次应用所有修复"""
        ...
```

Pipeline 流程变为：**LLM 生成 → ReportFixer.apply_all() → lint → gate**

#### 1.4 Fallback Ratio 阈值收紧

当前：≤0.20 PASS，0.20-0.35 WARN，>0.35 FAIL
目标：≤0.10 PASS，0.10-0.20 WARN，>0.20 FAIL

这需要同步改进各 layer 的 prompt，减少 fallback 依赖。

#### 1.5 实施步骤

- [ ] Step 1：写 ReportFixer 失败测试
- [ ] Step 2：实现 ReportFixer（CJK 标点、重复标题、表格列数）
- [ ] Step 3：在 report_writer.py 中插入 fixer + hard gate
- [ ] Step 4：在 scripts/run_case.py 的 pipeline 末端加 lint summary 输出
- [ ] Step 5：在 api/service.py 的 run_analysis 中加 lint gate
- [ ] Step 6：收紧 fallback ratio 阈值
- [ ] Step 7：跑 civil_loan pipeline，修复触发的新 lint 错误
- [ ] Step 8：全量测试 + 提交

#### 1.6 验收标准

- [ ] render contract ERROR 级别规则阻断 pipeline（抛异常）
- [ ] ReportFixer 能自动修复 CJK 标点、重复标题、表格列数不匹配
- [ ] fallback ratio ≤ 0.20 的报告才能通过（WARN 不阻断但记录）
- [ ] civil_loan case 的报告通过所有 10 条规则
- [ ] 全量测试通过

#### 1.7 工作量估计

~3-4 天。ReportFixer 本身简单，主要工作量在修复 LLM prompt 使 fallback ratio 达标。

---

### Phase 2：DOCX v3 集成

**目标**：用 v3 四层报告数据结构驱动 DOCX 生成，淘汰旧的直接渲染路径。

#### 2.1 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `engines/report_generation/v3/docx_v3_generator.py` | 新的 v3 DOCX 生成器 |
| 修改 | `engines/report_generation/docx_generator.py` | 标记为 deprecated，内部转发到 v3 生成器 |
| 新建 | `engines/report_generation/v3/docx_styles.py` | DOCX 样式常量和工具函数（从旧 generator 提取） |
| 修改 | `engines/report_generation/v3/report_writer.py` | 增加 `write_docx()` 方法 |
| 修改 | `scripts/run_case.py` | DOCX 生成走 v3 路径 |
| 修改 | `api/service.py` | API DOCX 生成走 v3 路径 |
| 新建 | `engines/report_generation/v3/tests/test_docx_v3.py` | DOCX v3 测试 |

#### 2.2 设计原则

旧路径：`原始数据 → docx_generator.py → DOCX`（跳过 v3 架构，内容和 MD 不一致）
新路径：`原始数据 → FourLayerReport → MD + DOCX`（同一数据源，语义对齐）

```python
# engines/report_generation/v3/docx_v3_generator.py

class DocxV3Generator:
    """从 FourLayerReport 生成 DOCX，与 Markdown 语义完全对齐。"""

    def __init__(self, report: FourLayerReport, style_config: DocxStyleConfig = None):
        self.report = report
        self.style = style_config or DocxStyleConfig()

    def generate(self, output_path: Path) -> Path:
        """生成 DOCX 文件，返回路径。"""
        doc = Document()
        self._setup_styles(doc)
        self._render_layer1_cover(doc)
        self._render_layer2_core(doc)
        self._render_layer3_perspective(doc)
        self._render_layer4_appendix(doc)
        self._add_disclaimer(doc)
        doc.save(str(output_path))
        return output_path

    def _render_layer1_cover(self, doc): ...
    def _render_layer2_core(self, doc): ...
    def _render_layer3_perspective(self, doc): ...
    def _render_layer4_appendix(self, doc): ...
```

#### 2.3 DOCX Render Contract

DOCX 也需要类似 Markdown 的质量检查：

```python
def lint_docx_render_contract(doc_path: Path) -> list[LintResult]:
    """从生成的 DOCX 提取文本后跑 render contract 子集。"""
    doc = Document(str(doc_path))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    # 复用 MD 的规则子集：forbidden_tokens, raw_json_leak, duplicate_heading
    ...
```

#### 2.4 实施步骤

- [ ] Step 1：从 docx_generator.py 提取样式常量到 docx_styles.py
- [ ] Step 2：写 DocxV3Generator 失败测试（输入 FourLayerReport mock，输出合法 DOCX）
- [ ] Step 3：实现 DocxV3Generator（四层渲染）
- [ ] Step 4：实现 DOCX render contract lint
- [ ] Step 5：修改 report_writer.py 增加 write_docx()
- [ ] Step 6：修改 pipeline（scripts/run_case.py + api/service.py）走 v3 DOCX 路径
- [ ] Step 7：旧 docx_generator.py 标记 deprecated，内部转发
- [ ] Step 8：跑 civil_loan pipeline，验证 MD 和 DOCX 内容对齐
- [ ] Step 9：全量测试 + 提交

#### 2.5 验收标准

- [ ] DOCX 从 FourLayerReport 生成，不再直接读原始数据
- [ ] DOCX 和 MD 的 section 标题、内容结构完全对应
- [ ] DOCX 通过 render contract 子集（forbidden_tokens, raw_json_leak, duplicate_heading）
- [ ] CJK 字体 fallback 正确（SimSun/Microsoft YaHei）
- [ ] pipeline 生成的 DOCX 能被 Word/LibreOffice 正常打开
- [ ] 旧 docx_generator.py 的 public API 保持向后兼容

#### 2.6 工作量估计

~4-5 天。DOCX 渲染细节多（表格、样式、字体），需要大量手动验证。

---

### Phase 3：多案型报告验收

**目标**：civil_loan / labor_dispute / real_estate 三种案型的报告全部通过 render contract + 内容完整性检查。

#### 3.1 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `outputs/acceptance/v3/` | v3 报告 golden artifacts |
| 新建 | `engines/report_generation/v3/tests/test_multi_case_type_reports.py` | 多案型报告集成测试 |
| 修改 | 各案型的 prompt 文件 | 优化 prompt 减少 fallback |
| 修改 | `engines/report_generation/v3/layer2_core.py` | 案型特化的 section 模板 |
| 修改 | `engines/report_generation/v3/layer3_perspective.py` | 案型特化的视角分析 |

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

#### 3.3 实施步骤

- [ ] Step 1：跑 civil_loan pipeline，记录 lint 结果
- [ ] Step 2：修复 civil_loan 的 lint 违规（prompt 优化 + fixer）
- [ ] Step 3：跑 labor_dispute pipeline，记录 lint 结果
- [ ] Step 4：修复 labor_dispute 特有问题（amount_calculation_report=None 路径）
- [ ] Step 5：跑 real_estate pipeline，记录 lint 结果
- [ ] Step 6：修复 real_estate 特有问题
- [ ] Step 7：三种案型的最终报告存为 golden artifacts
- [ ] Step 8：写集成测试对比 golden artifacts 的结构
- [ ] Step 9：全量测试 + 提交

#### 3.4 验收标准

- [ ] 三种案型的 MD 和 DOCX 报告全部通过 render contract
- [ ] fallback ratio 均 ≤ 0.20
- [ ] amount_calculation_report=None 的案型（labor_dispute, real_estate）不报错、不出空 section
- [ ] golden artifacts 存入 outputs/acceptance/v3/
- [ ] 集成测试验证报告结构（section 数量、标题列表、证据引用完整性）

#### 3.5 工作量估计

~4-5 天。每种案型需要完整 pipeline run（~25-30分钟），加上 prompt 调优迭代。

---

### Phase 4：报告恢复与幂等

**目标**：`--resume` 从持久化产物重新生成报告，结果与首次生成结构一致（幂等性）。

#### 4.1 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `scripts/run_case.py` | `--resume` 路径走 v3 report_writer |
| 修改 | `engines/report_generation/v3/report_writer.py` | `rebuild_from_artifacts()` 方法 |
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
    返回 (markdown_content, docx_path)。"""
    ...
```

幂等性定义：首次生成和 resume 生成的报告在**结构**上一致（section 标题和顺序相同），**内容**可能因时间戳等微调而有差异，但 render contract 结果相同。

#### 4.3 实施步骤

- [ ] Step 1：写恢复一致性失败测试（mock 产物目录 → rebuild → 对比结构）
- [ ] Step 2：实现 rebuild_from_artifacts()
- [ ] Step 3：修改 scripts/run_case.py 的 --resume 路径
- [ ] Step 4：跑一次完整 pipeline → resume → 对比
- [ ] Step 5：全量测试 + 提交

#### 4.4 验收标准

- [ ] `rebuild_from_artifacts()` 不调用 LLM
- [ ] resume 生成的报告通过 render contract
- [ ] resume 和首次生成的 section 标题列表完全一致
- [ ] resume 生成的 DOCX 结构与首次一致

#### 4.5 工作量估计

~2-3 天。

---

## 整体依赖关系

```
Phase 1 (Lint Gate + MD 质量)  ──────────────────→  必须先做
    │
    ├─► Phase 2 (DOCX v3 集成)   ← 依赖 Phase 1 的 fixer 和 gate
    │       │
    │       └─► Phase 3 (多案型验收) ← 依赖 Phase 1+2 的完整 pipeline
    │
    └─► Phase 4 (恢复与幂等)      ← 依赖 Phase 1 的 report_writer 变更
```

执行顺序：**Phase 1 → Phase 2 → Phase 3 → Phase 4**（严格顺序，每个 Phase 依赖前一个）

Phase 4 也可以和 Phase 3 并行（resume 逻辑独立于多案型验收）。

## 风险与缓解

| 风险 | 严重度 | 缓解 |
|------|--------|------|
| LLM 输出不稳定导致 fallback ratio 波动 | 高 | ReportFixer 自动修复 + prompt 模板固化 section 结构 |
| DOCX 渲染与 Word/LibreOffice 兼容性 | 中 | 用 python-docx 标准 API，避免直接操作 XML |
| 收紧阈值后现有 pipeline 大量失败 | 中 | 分步收紧：先 0.25，稳定后 0.20 |
| 多案型 pipeline run 耗时（每次 25-30 分钟） | 低 | 并行跑不同案型 |
| docx_generator.py 向后兼容 | 中 | 保留 public API，内部转发到 v3 |

## 总工作量估计

| Phase | 估计 |
|-------|------|
| Phase 1 Lint Gate + MD 质量 | 3-4 天 |
| Phase 2 DOCX v3 集成 | 4-5 天 |
| Phase 3 多案型报告验收 | 4-5 天 |
| Phase 4 报告恢复与幂等 | 2-3 天 |
| **合计** | **13-17 天** |

---

*计划版本：v3-draft · 生成日期：2026-04-06*
