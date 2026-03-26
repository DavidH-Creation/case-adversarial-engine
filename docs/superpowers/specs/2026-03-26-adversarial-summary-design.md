# AdversarialSummary 设计文档

**日期：** 2026-03-26
**版本：** v1.1
**目标：** 在三轮对抗结束后，用 LLM 对辩论全貌进行语义分析，产出结构化总结层。

---

## 背景

`RoundEngine.run()` 完成三轮对抗后，返回 `AdversarialResult`。当前结果中：

- `plaintiff_best_arguments` / `defendant_best_defenses`：纯规则提取（`_extract_best_arguments()`），无"为什么最强"推理。
- `unresolved_issues`：只有争点 ID 列表（`list[str]`），无未闭合原因说明。
- `missing_evidence_report`：`list[MissingEvidenceReport]`，只标记哪方缺证，无深度分析。
- 缺少 `overall_assessment`（整体态势评估）。

v1 roadmap 要求：
> 输出：原告最强论证、被告最强抗辩、关键争点未闭合列表、缺证报告

本设计补齐 LLM 语义分析层，以满足该要求。

---

## 架构决策

### 选择：`AdversarialSummarizer` 独立类 + `AdversarialResult.summary` 可选字段

**理由：**
- 单一职责：`RoundEngine` 负责编排，`AdversarialSummarizer` 负责语义总结。
- 向后兼容：`summary: Optional[AdversarialSummary] = None`，现有测试无需修改（仅需更新 LLM 调用次数断言）。
- 可独立测试：`AdversarialSummarizer` 可以单独 mock LLM 测试，无需跑完整三轮。
- `RoundEngine.run()` 内部自动调用 summarizer，调用方接口不变。
- 异常处理：summarizer 失败（超重试）抛出 `RuntimeError`，由 `run()` 向上传播（不静默失败）。

**放弃的方案：**
- 用 LLM 替换 `_extract_best_arguments()` 静态方法：破坏现有 5 次 LLM 调用结构。
- 作为独立管线阶段返回独立对象：增加调用方负担。

---

## Schema 设计

### 新增模型（`schemas.py`）

```python
class StrongestArgument(BaseModel):
    """LLM 分析识别的最强论点，与 Argument 平行但包含推理说明。"""
    issue_id: str = Field(..., min_length=1)
    position: str = Field(..., min_length=1)       # 论证文本，与 Argument.position 字段名一致
    evidence_ids: list[str] = Field(..., min_length=1)  # 支持证据 ID，非空
    reasoning: str = Field(..., min_length=1)       # 为什么是最强论证

class UnresolvedIssueDetail(BaseModel):
    """带原因说明的未闭合争点，LLM 分析的增强版（基础版仅有 issue_id 字符串）。"""
    issue_id: str = Field(..., min_length=1)
    issue_title: str = Field(..., min_length=1)
    why_unresolved: str = Field(..., min_length=1)  # 未闭合原因说明

class MissingEvidenceSummary(BaseModel):
    """LLM 增强的缺证分析，与规则层 MissingEvidenceReport 平行（不替代）。"""
    issue_id: str = Field(..., min_length=1)
    missing_for_party_id: str = Field(..., min_length=1)  # 与 MissingEvidenceReport 字段名一致
    gap_description: str = Field(..., min_length=1)       # 缺什么证据

class AdversarialSummary(BaseModel):
    """三轮对抗 LLM 语义分析总结产物。"""
    plaintiff_strongest_arguments: list[StrongestArgument]
    defendant_strongest_defenses: list[StrongestArgument]
    unresolved_issues: list[UnresolvedIssueDetail]          # 显式类型：list[UnresolvedIssueDetail]
    missing_evidence_report: list[MissingEvidenceSummary]
    overall_assessment: str = Field(..., min_length=1)      # 整体态势评估，非空
```

**命名对齐说明：**
- `StrongestArgument.position`：与现有 `Argument.position` 字段名一致，避免混淆。
- `MissingEvidenceSummary.missing_for_party_id`：与现有 `MissingEvidenceReport.missing_for_party_id` 一致。
- `MissingEvidenceSummary.gap_description`：**有意偏离** `MissingEvidenceReport.description`，`gap_description` 语义更精确（描述"缺口"而非通用描述），非笔误。
- `MissingEvidenceSummary` 是 LLM 增强层，`MissingEvidenceReport` 是规则层，两者共存于 `AdversarialResult`。

### `AdversarialResult` 变更

新增字段：
```python
summary: Optional[AdversarialSummary] = None
```

---

## `AdversarialSummarizer` 设计

**文件：** `engines/adversarial/summarizer.py`

### 接口

```python
class AdversarialSummarizer:
    def __init__(self, llm_client: LLMClient, config: RoundConfig) -> None

    async def summarize(
        self,
        result: AdversarialResult,
        issue_tree: IssueTree,
    ) -> AdversarialSummary
```

### Prompt 策略

**系统提示：**
- 角色：中立法律分析员，对三轮对抗辩论进行结构化总结
- 输出格式约束：严格 JSON，不输出任何解释文字

**用户提示内容：**
1. 案件基本信息（case_id、争点列表含 issue_id+title）
2. 三轮辩论摘要（5 个 AgentOutput 的 `output_id`, `agent_role_code`, `round_index`, `title`, `body`）
3. 已检测的证据冲突列表（`evidence_conflicts`）
4. 已检测的未决争点 ID（`unresolved_issues: list[str]`，作为参考上下文）
5. 已检测的缺证列表（`missing_evidence_report: list[MissingEvidenceReport]`）
6. 要求输出 JSON

**LLM 输出 JSON Schema（防退化约束）：**
```json
{
  "plaintiff_strongest_arguments": [
    {
      "issue_id": "（对应争点 ID，必须来自已知争点列表）",
      "position": "（原告最强论点，必须引用具体证据 ID）",
      "evidence_ids": ["（证据 ID 列表，非空）"],
      "reasoning": "（为什么这是最强论点，不超过 200 字）"
    }
  ],
  "defendant_strongest_defenses": [
    {
      "issue_id": "...",
      "position": "（被告最强抗辩，必须引用具体证据 ID）",
      "evidence_ids": ["（证据 ID 列表，非空）"],
      "reasoning": "（为什么这是最强抗辩，不超过 200 字）"
    }
  ],
  "unresolved_issues": [
    {
      "issue_id": "...",
      "issue_title": "（争点标题）",
      "why_unresolved": "（未闭合原因，不超过 150 字）"
    }
  ],
  "missing_evidence_report": [
    {
      "issue_id": "...",
      "missing_for_party_id": "（缺证方 party_id）",
      "gap_description": "（缺少什么证据，不超过 150 字）"
    }
  ],
  "overall_assessment": "（整体态势评估，不超过 300 字）"
}
```

### 重试与错误处理

- 最多 `config.max_retries` 次重试
- 超出后抛出 `RuntimeError`（与 `BasePartyAgent._call_llm_with_retry()` 一致）
- `RuntimeError` 由 `RoundEngine.run()` 向上传播，不静默失败（调用方需处理）
- JSON 解析通过 `_extract_json_object()`（与现有代码一致）

### 集成点（`RoundEngine.run()`）

在构建 `AdversarialResult` 之后，return 之前：
```python
summarizer = AdversarialSummarizer(self._llm, self._config)
summary = await summarizer.summarize(result, issue_tree)
return result.model_copy(update={"summary": summary})
```

---

## 测试设计

**文件：** `engines/adversarial/tests/test_summarizer.py`（新建）

### Mock LLM 响应

```json
{
  "plaintiff_strongest_arguments": [
    {
      "issue_id": "issue-001",
      "position": "原告有转账记录，证明借款已实际交付",
      "evidence_ids": ["ev-001"],
      "reasoning": "直接证明借贷要件"
    }
  ],
  "defendant_strongest_defenses": [
    {
      "issue_id": "issue-001",
      "position": "被告否认收款",
      "evidence_ids": ["ev-001"],
      "reasoning": "动摇借贷成立基础"
    }
  ],
  "unresolved_issues": [
    {
      "issue_id": "issue-001",
      "issue_title": "借贷关系是否成立",
      "why_unresolved": "双方证据存在正面冲突，未有定论"
    }
  ],
  "missing_evidence_report": [
    {
      "issue_id": "issue-001",
      "missing_for_party_id": "party-d-001",
      "gap_description": "被告缺乏收款否认的书面证据"
    }
  ],
  "overall_assessment": "原告证据链较完整，被告抗辩薄弱，但争点尚未闭合。"
}
```

### 测试用例

| 测试 | 验证内容 |
|------|---------|
| `test_summarize_returns_adversarial_summary` | 返回类型为 `AdversarialSummary` |
| `test_plaintiff_strongest_arguments_populated` | `plaintiff_strongest_arguments` 非空 |
| `test_defendant_strongest_defenses_populated` | `defendant_strongest_defenses` 非空 |
| `test_unresolved_issues_have_why_unresolved` | 每条 `UnresolvedIssueDetail` 含非空 `why_unresolved` |
| `test_missing_evidence_populated` | `missing_evidence_report` 非空 |
| `test_overall_assessment_non_empty` | `overall_assessment` 非空字符串（`min_length=1` 约束） |
| `test_evidence_ids_non_empty_in_arguments` | 所有 `StrongestArgument.evidence_ids` 非空 |
| `test_llm_called_once` | Summarizer 只调用一次 LLM |
| `test_runtime_error_on_repeated_llm_failure` | 超重试次数抛 `RuntimeError` |

**集成测试（`test_round_engine.py` 新增）：**

| 测试 | 验证内容 |
|------|---------|
| `test_result_includes_summary` | `result.summary` 类型为 `AdversarialSummary`（非 None） |
| 更新 `test_llm_called_five_times` → `test_llm_called_six_times` | 加入 summarizer 后共 6 次 LLM 调用 |

**`SequentialMockLLM._responses` 扩展要求：**

`test_round_engine.py` 中的 `SequentialMockLLM` 目前有 5 条响应（5 次 LLM 调用）。
加入 summarizer 后，`RoundEngine.run()` 新增第 6 次 LLM 调用。
必须将 `_responses` 扩展为 6 条，第 6 条为有效的 `AdversarialSummary` JSON（与 `test_summarizer.py` mock 响应一致）：

```json
{
  "plaintiff_strongest_arguments": [
    {
      "issue_id": "issue-001",
      "position": "原告有转账记录，证明借款已实际交付",
      "evidence_ids": ["ev-001"],
      "reasoning": "直接证明借贷要件"
    }
  ],
  "defendant_strongest_defenses": [
    {
      "issue_id": "issue-001",
      "position": "被告否认收款，质疑转账用途",
      "evidence_ids": ["ev-001"],
      "reasoning": "动摇借贷成立基础"
    }
  ],
  "unresolved_issues": [
    {
      "issue_id": "issue-001",
      "issue_title": "借贷关系是否成立",
      "why_unresolved": "双方证据存在正面冲突，未有定论"
    }
  ],
  "missing_evidence_report": [
    {
      "issue_id": "issue-001",
      "missing_for_party_id": "party-d-001",
      "gap_description": "被告缺乏收款否认的书面证据"
    }
  ],
  "overall_assessment": "原告证据链较完整，被告抗辩薄弱，但争点尚未闭合。"
}
```

不扩展 `_responses` 会导致第 6 次调用返回 `_responses[0]`（原告主张 JSON），`AdversarialSummary` 解析失败。

---

## 文件变更列表

| 文件 | 操作 |
|------|------|
| `engines/adversarial/schemas.py` | 新增 `StrongestArgument`, `UnresolvedIssueDetail`, `MissingEvidenceSummary`, `AdversarialSummary` + `AdversarialResult.summary` 字段 |
| `engines/adversarial/summarizer.py` | 新建 `AdversarialSummarizer` 类 |
| `engines/adversarial/round_engine.py` | 在 `run()` 末尾调用 summarizer |
| `engines/adversarial/__init__.py` | 导出 `AdversarialSummarizer`, `AdversarialSummary` |
| `engines/adversarial/tests/test_summarizer.py` | 新建测试文件（9 个测试） |
| `engines/adversarial/tests/test_round_engine.py` | 更新：新增 2 个测试，更新 LLM 调用次数断言（5→6） |

---

## 合约保证

- `AdversarialSummary.plaintiff_strongest_arguments` 每条的 `evidence_ids` 非空（`min_length=1`）
- `overall_assessment: str = Field(..., min_length=1)`（非空约束）
- Summarizer LLM 失败超重试 → `RuntimeError`，由 `run()` 传播（不静默失败）
- `MissingEvidenceSummary` 与 `MissingEvidenceReport` 共存：前者为 LLM 增强层，后者为规则层
- `StrongestArgument.position` 字段名与 `Argument.position` 一致（避免命名歧义）
