# V2 Closing Plan

> 状态：DRAFT
> 作者：Claude (based on review gaps)
> 日期：2026-04-04

---

## Gap 坐实结论

### Gap 2：Public API ID Contract 漂移（坐实结果）

**严重程度：中等 — 一处语义 bug + 一处 URL 设计缺陷 + 一处代码重复声明**

核心问题在 `api/app.py:447`：

```python
# GET /api/cases/{case_id}/artifacts
return {"run_id": case_id, "artifacts": list_artifacts(record)}
```

`case_id`（格式 `case-xxxx`）被冒充为 `run_id`（格式 `run-xxxx`）返回。这两个 ID 语义完全不同：

| ID | 语义 | 生成时机 | 格式 |
|----|------|----------|------|
| `case_id` | 案件标识，跨分析持久 | `POST /cases/` 时生成 | `case-{uuid[:12]}` |
| `run_id` | 单次分析运行标识 | 分析完成后生成 | `run-{uuid[:12]}` |

**影响链路**：如果消费者拿 artifacts 返回的 `run_id`（实际是 case_id）去调 `POST /scenarios/run`，会得到 404（`run_id 不存在: case-xxx`）。目前前端没有调 artifacts 端点，所以无用户面直接故障，但这是一个 API contract 时间炸弹。

**全部 ID 混用清单**：

| 位置 | 问题 | 修复方案 |
|------|------|----------|
| `app.py:447` | `"run_id": case_id` | 改为 `"case_id": case_id` |
| `app.py:344` | `/api/cases/{run_id}/progress` — 路径参数用 `run_id` 但 URL 在 `/cases/` 下 | 参数名改为 `case_id`，或迁移到 `/api/runs/{run_id}/progress` |
| `service.py:88-90` | `self.run_id` 重复声明两次 | 删除第一个 |
| `test_analysis_endpoints.py:93` | `assert data["run_id"] == record.case_id` — 测试把 bug 编纂为正确行为 | 改为 `assert data["case_id"] == record.case_id` |

**结论**：这不是深层语义混用，而是一处表面赋值错误 + 一处 URL 设计遗留。修复范围可控：1 行代码 + 1 行测试 + 2 处可选清理。列为 Phase 0c，优先级低于 Gap 1/3。

---

## 优先级排序

```
Gap 1（render user-clean）≈ Gap 3（真实多案型 behavior acceptance）> Gap 2（API ID contract）
```

理由：Gap 1/3 直接影响交付物质量和多案型置信度；Gap 2 是内部 API 一致性，当前无外部消费者受损。

---

## Phase 0a：Render User-Clean Gate

**目标**：将 render contract 从 "format-clean"（不泄露内部 token）升级到 "user-clean"（人类读者看到的就是成品质量）。

### 当前 render_contract 覆盖范围（format-clean）

`engines/report_generation/v3/render_contract.py` 当前检查三项：
1. 禁止内部 token（`issue-*`、`xexam-*`、`undefined`、`PATH-*`）
2. 空的 `##` 大章节
3. 全占位表格行

### 需要新增的 lint rules（升级到 user-clean）

| 规则 | 检测内容 | 严重度 |
|------|----------|--------|
| `raw_json_leak` | Markdown 中出现裸 JSON（`{"`、`[{"`）| ERROR |
| `orphan_citation` | 引用标记 `[src-xxx]` 在证据索引中不存在 | ERROR |
| `excessive_fallback` | 整篇报告中 fallback 占位段（如 "*暂无*"）占比超阈值 | WARN |
| `section_length_floor` | 核心章节（争点地图、对抗辩论、证据索引）内容 < 50 字 | WARN |
| `duplicate_heading` | 同级 `##` 标题重复 | ERROR |
| `table_header_mismatch` | 表格数据行列数 ≠ 表头列数 | ERROR |
| `cjk_punctuation_mix` | 中英文标点混用（如句号后跟英文句点）| WARN |

### Fallback Ratio 阈值建议

当前没有集中的 fallback_ratio 指标。实现方案：

1. 在 `_fill_empty_major_sections()` 返回值中附带 fallback 计数
2. 定义指标：`fallback_ratio = fallback_sections / total_major_sections`
3. 阈值：
   - **PASS**: fallback_ratio ≤ 0.20（最多 20% 章节使用占位）
   - **WARN**: 0.20 < fallback_ratio ≤ 0.35
   - **FAIL**: fallback_ratio > 0.35

### Checked-in Sample Report 升级标准

当前样本：`outputs/20260328-180421/`（civil_loan 完整输出）

升级标准：
- 所有 checked-in sample 必须通过完整 user-clean lint（新旧规则全部 0 violation）
- 每种 case_type 至少一份通过 user-clean 的 golden report
- Sample 纳入 CI：`pytest tests/ -k render_contract` 覆盖所有 checked-in 样本

### 预估工作量

| 子任务 | 工作量 |
|--------|--------|
| 新增 7 条 lint rules | 1 session |
| fallback_ratio 集成到 report_writer | 0.5 session |
| 现有 sample 修复至 user-clean | 0.5 session |
| CI 集成 | 0.5 session |
| **合计** | **~2.5 sessions** |

### Definition of Done

- [ ] `lint_markdown_render_contract()` 包含全部 10 条规则（原 3 + 新 7）
- [ ] `fallback_ratio` 作为 `write_v3_report_md()` 返回值的一部分可供检查
- [ ] `outputs/` 下所有 checked-in 报告通过 user-clean lint
- [ ] `npx tsc --noEmit` / `pytest` 零失败

---

## Phase 0b：真实多案型 Behavior Acceptance

**目标**：至少 civil_loan、labor_dispute、real_estate 各一个案例通过完整 acceptance 验收。

### 当前状态

- **Acceptance 框架**：`tests/acceptance/test_v2_acceptance.py` + `scripts/run_acceptance.py` 已就绪
- **Case YAML 库**：
  - `civil_loan`: `wang_v_chen_zhuang_2025.yaml`, `wang_zhang_2022.yaml`
  - `labor_dispute`: `labor_dispute_{1,2,3}.yaml`
  - `real_estate`: `real_estate_{1,2,3}.yaml`
- **问题**：框架和 YAML 都有，但没有跑过真实模型的验收记录

### 执行方案

**方式：Recorded Artifacts 优先，真实模型补充**

1. **Phase 0b-1：Recorded Artifacts 验收**（offline，不消耗 API）
   - 对每种 case_type 选一个代表案例，用 `scripts/run_case.py` 本地跑一次完整 pipeline
   - 将 `outputs/{run_id}/` 全部产物 commit 为 golden artifacts
   - 验收脚本从 golden artifacts 计算指标，确认框架工作正常

2. **Phase 0b-2：真实模型 N=3 验收**（online，消耗 API）
   - 对通过 0b-1 的案例，跑 `scripts/run_acceptance.py --n=3`
   - 收集 consistency / citation_rate / path_explainable 指标

### 验收指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| **issue_tree_stability** | consistency ≥ 0.75 | N 次运行中，top-5 争点序列的最高频率 |
| **citation_completeness** | citation_rate = 1.0 | 每个 output slot 都有证据引用 |
| **render_cleanliness** | user-clean lint 0 violation | Phase 0a 的 lint 全部通过 |
| **fallback_ratio** | ≤ 0.20 | 报告中 fallback 占位不超过 20% |
| **path_explainable** | true | 决策树 + 报告同时存在且可追溯 |
| **n_success** | ≥ 3 | 至少 3 次成功运行 |

### 每个 case_type 的代表案例

| Case Type | YAML | 特征 |
|-----------|------|------|
| `civil_loan` | `wang_v_chen_zhuang_2025.yaml` | 民间借贷纠纷，已有完整输出样本 |
| `labor_dispute` | `labor_dispute_1.yaml` | 劳动争议，需验证 |
| `real_estate` | `real_estate_1.yaml` | 房产纠纷，需验证 |

### 预估工作量

| 子任务 | 工作量 |
|--------|--------|
| 0b-1：Golden artifacts 录制（3 案型） | 1 session（主要是等 API） |
| 0b-1：验收脚本对接 golden artifacts | 0.5 session |
| 0b-2：N=3 真实验收运行 | 1 session（API 时间为主） |
| 结果分析 + 修复不通过的案型 | 1-2 sessions |
| **合计** | **~3.5-4.5 sessions** |

### Definition of Done

- [ ] civil_loan、labor_dispute、real_estate 各至少一个案例通过 N=3 acceptance
- [ ] 所有指标达标：consistency ≥ 0.75, citation_rate = 1.0, fallback_ratio ≤ 0.20, path_explainable = true
- [ ] 验收结果和 golden artifacts 已 commit 到仓库
- [ ] `scripts/run_acceptance.py` 可在 CI 中以 recorded 模式运行

---

## Phase 0c：Public API ID Contract 修复

**目标**：消除 case_id / run_id 语义漂移，确保 API 响应中 ID 类型与字段名一致。

### 修复清单

| # | 文件 | 行 | 修复内容 |
|---|------|----|----------|
| 1 | `api/app.py` | 447 | `"run_id": case_id` → `"case_id": case_id` |
| 2 | `api/app.py` | 344 | `{run_id}` → `{case_id}` 并在函数体内相应调整 |
| 3 | `api/service.py` | 88 | 删除第一个 `self.run_id = None`（重复声明） |
| 4 | `api/tests/test_analysis_endpoints.py` | 93 | `data["run_id"]` → `data["case_id"]` |

### 连锁影响检查

- 前端 `index.html`：不调用 artifacts 端点，无影响
- Scenario API：使用真实 `run_id`（`run-xxx`），不受影响
- Progress endpoint 如果改参数名：需检查 `engines/shared/progress_reporter.py` 内部 key 是否依赖 `run_id` 字符串

### 预估工作量

| 子任务 | 工作量 |
|--------|--------|
| 修复 4 处代码 + 测试 | 0.5 session |
| 跑 `pytest api/tests/` 验证 | included |
| **合计** | **~0.5 session** |

### Definition of Done

- [ ] artifacts 端点返回 `case_id` 而非 `run_id`
- [ ] 无 case_id 冒充 run_id 的路径
- [ ] `self.run_id` 不再重复声明
- [ ] `pytest api/tests/` 全部通过
- [ ] progress 端点路径参数与实际语义一致

---

## 附加：DOCX Gate 对齐

**目标**：确保 DOCX 输出与 Markdown 报告质量对齐，不出现 Markdown 通过 user-clean 但 DOCX 丢失内容的情况。

### 当前状态

`engines/report_generation/docx_generator.py` 有 10+ 处 V3.0 backward-compatibility fallback，从 `analysis_data` dict 中取值的路径与 V3 report_writer 的输出结构有差异风险。

### 需要做的事

1. **DOCX 内容完整性测试**：对 golden artifacts 同时生成 MD + DOCX，断言 DOCX section 数量 ≥ MD `##` 数量
2. **DOCX fallback 审计**：检查每个 fallback 分支是否还有活路径，清除死代码
3. **CJK 字体覆盖**：确保 DOCX 在无 Microsoft YaHei 的环境下不崩溃

### 预估工作量

| 子任务 | 工作量 |
|--------|--------|
| DOCX 内容完整性断言 | 0.5 session |
| Fallback 审计 + 清理 | 0.5 session |
| 字体 fallback 测试 | 0.5 session |
| **合计** | **~1.5 sessions** |

### Definition of Done

- [ ] Golden artifacts 的 DOCX 输出包含所有 MD 中的大章节
- [ ] DOCX generator 中 dead fallback 分支已清除
- [ ] 无 Microsoft YaHei 的环境下 DOCX 生成不抛异常

---

## 总览

| Phase | 目标 | 预估 | 优先级 |
|-------|------|------|--------|
| 0a | Render User-Clean Gate | ~2.5 sessions | HIGH |
| 0b | 真实多案型 Behavior Acceptance | ~3.5-4.5 sessions | HIGH |
| 0c | Public API ID Contract | ~0.5 session | MEDIUM |
| 附加 | DOCX Gate 对齐 | ~1.5 sessions | MEDIUM |
| **总计** | | **~8-9 sessions** | |

### 建议执行顺序

```
0a (render lint) → 0b (acceptance — 依赖 0a 的 lint) → 0c (API fix) → DOCX gate
      ↑                        ↑
  可以和 0c 并行          依赖 0a 完成
```

0a 和 0c 可并行。0b 依赖 0a（因为 render_cleanliness 是验收指标之一）。DOCX gate 在 0a 之后。
