"""
IssueCategoryClassifier — 争点类型分类模块主类。
Issue Category Classifier — main class for P1.6 issue category classification.

职责 / Responsibilities:
1. 接收 IssueTree + EvidenceIndex + AmountCalculationReport
2. 一次性调用 LLM 对所有争点进行批量分类（四类）
3. 规则层：解析枚举、校验 category_basis 非空、校验 calculation_issue 关联 claim entry
4. 返回富化后的 IssueCategoryClassificationResult

合约保证 / Contract guarantees:
- issue_category 必须枚举值，否则清空并记入 unclassified
- category_basis 为空时清空 issue_category 并记入 unclassified
- calculation_issue 时 related_claim_entry_ids 必须有 ≥1 条已知 claim_id，否则清空并记入 unclassified
- LLM 返回未知 issue_id 被过滤忽略
- LLM 整体失败返回 failed 结果（原始顺序，全部争点进 unclassified），不抛异常
- 空争点树不调用 LLM，直接返回
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from engines.shared.models import (
    Issue,
    IssueCategory,
    LLMClient,
)

from engines.shared.structured_output import call_structured_llm

from .schemas import (
    IssueCategoryClassificationResult,
    IssueCategoryClassifierInput,
    LLMIssueCategoryItem,
    LLMIssueCategoryOutput,
)

# tool_use JSON Schema（模块加载时计算一次）
_TOOL_SCHEMA: dict = LLMIssueCategoryOutput.model_json_schema()


class IssueCategoryClassifier:
    """争点类型分类器。

    Args:
        llm_client:  符合 LLMClient 协议的客户端实例
        case_type:   案由类型，默认 "civil_loan"
        model:       LLM 模型名称
        temperature: LLM 温度参数
        max_tokens:  LLM 最大输出 token 数
        max_retries: LLM 调用失败时的最大重试次数
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """加载案由对应的 prompt 模板模块。"""
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(f"不支持的案由类型: '{case_type}'。可用: {available}")
        return PROMPT_REGISTRY[case_type]

    async def classify(
        self, inp: IssueCategoryClassifierInput
    ) -> IssueCategoryClassificationResult:
        """执行争点类型分类。

        Args:
            inp: 分类器输入（含争点树、证据索引、金额报告）

        Returns:
            IssueCategoryClassificationResult — 含填充了 issue_category 的争点树
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        issues = list(inp.issue_tree.issues)

        # 空争点树：直接返回，不调用 LLM
        if not issues:
            return IssueCategoryClassificationResult(
                classified_issue_tree=inp.issue_tree,
                classification_metadata={},
                unclassified_issue_ids=[],
                created_at=now,
            )

        known_issue_ids: set[str] = {i.issue_id for i in issues}
        known_claim_entry_ids: set[str] = (
            {e.claim_id for e in inp.amount_calculation_report.claim_calculation_table}
            if inp.amount_calculation_report is not None
            else set()
        )

        try:
            # 构建 prompt
            from .prompts import plugin

            system_prompt = self._prompt_module.SYSTEM_PROMPT
            user_prompt = plugin.get_prompt(
                "issue_category_classifier",
                self._case_type,
                {
                    "issue_tree": inp.issue_tree,
                    "evidence_index": inp.evidence_index,
                    "amount_calculation_report": inp.amount_calculation_report,
                },
            )

            # 调用 LLM（结构化输出）
            raw_dict = await self._call_llm_structured(system_prompt, user_prompt)
            llm_output = LLMIssueCategoryOutput.model_validate(raw_dict)

            # 规则层：校验 + 富化
            classified_issues, unclassified = self._apply_classifications(
                issues=issues,
                classifications=llm_output.classifications,
                known_issue_ids=known_issue_ids,
                known_claim_entry_ids=known_claim_entry_ids,
            )

            classified_tree = inp.issue_tree.model_copy(update={"issues": classified_issues})
            return IssueCategoryClassificationResult(
                classified_issue_tree=classified_tree,
                classification_metadata={
                    "model": self._model,
                    "temperature": self._temperature,
                    "classified_count": len(issues) - len(unclassified),
                    "total_count": len(issues),
                    "created_at": now,
                },
                unclassified_issue_ids=unclassified,
                created_at=now,
            )

        except Exception:
            # LLM 调用或解析失败：原始 issue_tree 保持原顺序，所有分类字段为 None
            return IssueCategoryClassificationResult(
                classified_issue_tree=inp.issue_tree,
                classification_metadata={"failed": True, "created_at": now},
                unclassified_issue_ids=[i.issue_id for i in issues],
                created_at=now,
            )

    # ------------------------------------------------------------------
    # 规则层：校验 + 富化 / Validation and enrichment
    # ------------------------------------------------------------------

    def _apply_classifications(
        self,
        issues: list[Issue],
        classifications: list[LLMIssueCategoryItem],
        known_issue_ids: set[str],
        known_claim_entry_ids: set[str],
    ) -> tuple[list[Issue], list[str]]:
        """将 LLM 分类结果校验后富化到 Issue 对象。

        校验失败规则（任一失败 → 清空 issue_category，记入 unclassified_issue_ids）：
        - issue_category: 必须是合法枚举值
        - category_basis: 必须非空
        - calculation_issue: related_claim_entry_ids 必须含 ≥1 条已知 claim_id

        Returns:
            (classified_issues, unclassified_issue_ids)
        """
        # 构建 cls_map（过滤未知 issue_id）
        cls_map: dict[str, LLMIssueCategoryItem] = {
            item.issue_id: item for item in classifications if item.issue_id in known_issue_ids
        }

        classified: list[Issue] = []
        unclassified: list[str] = []

        for issue in issues:
            item = cls_map.get(issue.issue_id)
            if item is None:
                # LLM 未返回该争点的分类
                unclassified.append(issue.issue_id)
                classified.append(issue)
                continue

            category = self._resolve_issue_category(item.issue_category)
            basis = item.category_basis.strip()

            # 校验 category 合法性
            if category is None:
                unclassified.append(issue.issue_id)
                classified.append(issue)
                continue

            # 校验 basis 非空
            if not basis:
                unclassified.append(issue.issue_id)
                classified.append(issue)
                continue

            # 校验 calculation_issue 关联
            if category == IssueCategory.calculation_issue:
                valid_entries = [
                    cid for cid in item.related_claim_entry_ids if cid in known_claim_entry_ids
                ]
                if not valid_entries:
                    unclassified.append(issue.issue_id)
                    classified.append(issue)
                    continue

            classified.append(issue.model_copy(update={"issue_category": category}))

        return classified, unclassified

    # ------------------------------------------------------------------
    # 枚举解析辅助 / Enum resolution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_issue_category(raw: str) -> Optional[IssueCategory]:
        _MAP = {
            "fact_issue": IssueCategory.fact_issue,
            "legal_issue": IssueCategory.legal_issue,
            "calculation_issue": IssueCategory.calculation_issue,
            "procedure_credibility_issue": IssueCategory.procedure_credibility_issue,
        }
        return _MAP.get(raw.strip().lower())

    # ------------------------------------------------------------------
    # LLM 调用（带重试）/ LLM call with retry
    # ------------------------------------------------------------------

    async def _call_llm_structured(self, system: str, user: str) -> dict:
        """调用 LLM（结构化输出），失败时抛出异常由 classify() 捕获。"""
        return await call_structured_llm(
            self._llm,
            system=system,
            user=user,
            model=self._model,
            tool_name="classify_issue_categories",
            tool_description="对案件所有争点进行批量分类（事实争点、法律争点、计算争点、程序信用争点）。"
            "Batch-classify all case issues into four categories: "
            "fact_issue, legal_issue, calculation_issue, procedure_credibility_issue.",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )
