> Historical document.
> Archived during the April 2026 documentation reorganization.
> Kept for context only. Do not treat this file as the current source of truth.
# v1 Completion Report

**版本**：v1.0
**完成日期**：2026-03-26
**基准版本**：v0.5（39/39 验收，280 测试）

---

## 1. Must Have 完成情况

| # | Must Have 项 | 完成状态 | 实现位置 |
|---|--------------|----------|----------|
| MH-1 | `CaseManager` | ✅ | `engines/shared/case_manager.py` |
| MH-2 | `JobManager` | ✅ | `engines/shared/job_manager.py` |
| MH-3 | 案件上下文持久化 | ✅ | `WorkspaceManager.save_agent_output()` + private 子目录 |
| MH-4 | 长任务状态机 | ✅ | `JobManager`（6 状态 10 条迁移路径）|
| MH-5 | `private/shared` 目录隔离 | ✅ | `AccessController` + workspace `artifacts/private/{party_id}/` |
| MH-6 | 固定回合（首轮主张、证据提交、针对性反驳）| ✅ | `RoundEngine`（三轮编排）|
| MH-7 | 输出：原告最强论证、被告最强抗辩、未闭合争点、缺证报告 | ✅ | `AdversarialSummary`（LLM 语义分析层）|
| MH-8 | 所有论点强制引用具体 `evidence_id` | ✅ | `AgentOutput.evidence_citations`（Pydantic 验证器）|

**结论：8/8 Must Have 全部完成。**

---

## 2. 测试覆盖情况

| 范围 | 测试文件 | 测试数 |
|------|----------|--------|
| 对抗代理（原告/被告/证据管理员）| `engines/adversarial/tests/test_agents.py` | ~20 |
| RoundEngine 三轮编排 | `engines/adversarial/tests/test_round_engine.py` | ~14 |
| AdversarialSummarizer | `engines/adversarial/tests/test_summarizer.py` | ~10 |
| 端到端对抗流程集成 | `tests/integration/test_adversarial_pipeline.py` | ~5 |
| AccessController（单元）| `engines/shared/tests/test_access_controller.py` | 已有 |
| JobManager（单元）| `engines/shared/tests/test_job_manager.py` | 已有 |
| v0.5 全量测试（零回归）| 全部 | 412 → 461（加入 adversarial/tests 后）|

**新增集成测试覆盖点**：
- `test_adversarial_pipeline_happy_path`：mock LLM 驱动完整三轮对抗 + AdversarialSummary 生成
- `test_access_controller_plaintiff_isolation`：验证原告代理无法看到被告 owner_private 证据
- `test_access_controller_defendant_isolation`：验证被告代理无法看到原告 owner_private 证据
- `test_adversarial_summary_required_fields`：AdversarialSummary 必须包含 5 个字段
- `test_round_engine_produces_three_rounds`：RoundEngine 输出恰好包含 3 个 RoundState

---

## 3. 已知限制和技术债务

### 3.1 功能限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| 无法重复性验收 | v1 Acceptance 要求"5 次重复运行，争点树一致性 >= 75%"，未实现自动化脚本 | 中 |
| 无 v1 验收脚本 | 类似 `scripts/verify_v05.py`，v1 缺少对应的 `scripts/verify_v1.py` | 中 |
| `procedure_setup` 未激活到对抗 pipeline | RoundEngine 未消费 `ProcedurePlanner` 的输出，直接使用固定三回合 | 低（v1 规格允许）|
| `CaseManager` 范围窄 | 目前只做多案件目录索引，未实现案件删除与归档 | 低 |

### 3.2 技术债务

| 债务项 | 说明 | 影响范围 |
|--------|------|----------|
| `pyproject.toml` 版本未更新 | 仍为 `0.5.0`，应升为 `1.0.0` | 打包/发布 |
| `AgentOutput` JSON Schema 未同步 | `schemas/` 下缺少 `agent_output.schema.json` | 合同文档 |
| `AdversarialResult` 持久化路径未规范化 | `artifact_index` 尚未为 `AdversarialResult` 增加键 | 回放能力 |
| 提示词未经系统性评测 | party_agent prompt 仅在单元测试中以 mock LLM 验证，无真实 LLM 输出质量基线 | 输出稳定性 |
| `engines/adversarial/tests` 原未加入 `testpaths` | v1 收尾时修复 | 已修复 ✅ |

---

## 4. 对 v1.5 的建议

v1.5 目标：程序化庭前会议 / 质证版。

### 4.1 必须先做（阻塞 v1.5 开始）

1. **`evidence_state_machine`**：证据状态（提交 → 采纳 → 质疑 → 排除）是 v1.5 质证的基础。`EvidenceStatus` 枚举已在 `models.py` 中定义，但状态迁移逻辑尚未实现。
2. **`JudgeAgent`**：v1.5 需要程序法官发问机制，其输入格式（只读 admitted_record）已由 `AccessController` 预留。

### 4.2 建议的设计原则

- **不要新建独立引擎**：v1.5 的 `JudgeAgent` 应接入现有 `RoundEngine` 作为第四个角色，而非新起一条执行路径。
- **evidence_state 应在 `EvidenceIndex` 级别追踪**：不要把状态散落在 `AgentOutput` 里。
- **质证模板先从单一角度切入**：先做"真实性"维度质证，再扩展关联性、合法性、证明力。

### 4.3 可直接复用的 v1 资产

| v1 资产 | v1.5 用途 |
|---------|-----------|
| `AccessController` | 法官只读 admitted_record 的权限控制 |
| `RoundEngine` | 增加第 4 轮（法官追问轮）|
| `JobManager` | 追踪更长的庭前会议流程 |
| `AdversarialSummary` 结构 | 扩展为《质证焦点清单》|
| `EvidenceStatus` 枚举 | 直接用于 evidence_state_machine 初始状态 |

---

## 5. v1 Acceptance 标准对照

| 验收标准 | 验证方式 | 结果 |
|----------|----------|------|
| 同一案件重复运行 5 次，争点树一致性 >= 75% | temperature=0.0 约束 + 待补 verify_v1.py | ⚠️ 未自动化验收 |
| 对抗后新增发现的关键缺证点比例显著高于 v0.5 | 人工对比评估（基于 benchmark 样本）| ⚠️ 待评估 |
| 所有论点必须引用具体证据编号 | `AgentOutput.evidence_citations` Pydantic 验证器 | ✅ 代码保证 |
| 原被告无法读取对方 `owner_private` 材料 | `test_access_controller_*_isolation` 集成测试 | ✅ 测试覆盖 |
| 案件和任务状态可恢复、可回放 | `JobManager` + `WorkspaceManager` + checkpoint 机制 | ✅ 实现 + 单元测试 |

---

*本报告由 Claude Code 自动生成。2026-03-26。*

