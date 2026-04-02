"""
相关性排序器 — 用 LLM 对候选类案做语义相关性排序。
Relevance ranker — uses LLM to rank candidate cases by semantic relevance.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

from engines.shared.structured_output import call_structured_llm
from .schemas import CaseIndexEntry, LLMRankedItem, RankedCase, RelevanceScore

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一名资深中国法律案例研究专家。给定一个当前案件和若干候选类案，请从以下四个维度评估每个候选案例与当前案件的相关性：

1. 事实相似度 (fact_similarity): 案件基本事实是否相似
2. 法律关系相似度 (legal_relation_similarity): 涉及的法律关系是否相同
3. 争议焦点相似度 (dispute_focus_similarity): 争议焦点是否一致
4. 裁判参考价值 (judgment_reference_value): 该案判决对当前案件的参考意义

每个维度评分 0.0-1.0，并给出综合评分 (overall) 和简要分析。
按综合评分从高到低排序输出。

你必须以严格 JSON 格式输出，不得包含任何 Markdown 标记、代码块、表格或其他非 JSON 内容。
输出格式示例：
{
  "ranked_cases": [
    {
      "case_number": "（2021）京02民终1234号",
      "fact_similarity": 0.8,
      "legal_relation_similarity": 0.7,
      "dispute_focus_similarity": 0.6,
      "judgment_reference_value": 0.75,
      "overall": 0.72,
      "analysis": "该案与本案均涉及民间借贷中的借款主体争议..."
    }
  ]
}
"""

_TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "ranked_cases": {
            "type": "array",
            "description": "按相关性排序的案例列表",
            "items": {
                "type": "object",
                "properties": {
                    "case_number": {"type": "string", "description": "案号"},
                    "fact_similarity": {"type": "number"},
                    "legal_relation_similarity": {"type": "number"},
                    "dispute_focus_similarity": {"type": "number"},
                    "judgment_reference_value": {"type": "number"},
                    "overall": {"type": "number"},
                    "analysis": {"type": "string", "description": "相关性分析"},
                },
                "required": [
                    "case_number",
                    "fact_similarity",
                    "legal_relation_similarity",
                    "dispute_focus_similarity",
                    "judgment_reference_value",
                    "overall",
                    "analysis",
                ],
            },
        }
    },
    "required": ["ranked_cases"],
}


class RelevanceRanker:
    """用 LLM 对候选类案进行语义相关性排序。"""

    def __init__(
        self,
        llm_client: "LLMClient",
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

    async def rank(
        self,
        case_data: dict[str, Any],
        candidates: list[CaseIndexEntry],
    ) -> list[RankedCase]:
        """对候选案例做语义相关性排序，返回按 overall 降序排列的结果。"""
        if not candidates:
            return []

        user_prompt = self._build_user_prompt(case_data, candidates)
        logger.info("对 %d 条候选类案进行语义排序...", len(candidates))

        data = await call_structured_llm(
            self._llm,
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            model=self._model,
            tool_name="rank_similar_cases",
            tool_description="对候选类案进行语义相关性评分和排序",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )

        entry_map = {e.case_number: e for e in candidates}
        ranked_items = [LLMRankedItem.model_validate(item) for item in data.get("ranked_cases", [])]

        results: list[RankedCase] = []
        for item in ranked_items:
            entry = entry_map.get(item.case_number)
            if entry is None:
                logger.warning("LLM 返回的案号未在候选列表中: %s", item.case_number)
                continue
            results.append(
                RankedCase(
                    case=entry,
                    relevance=RelevanceScore(
                        fact_similarity=item.fact_similarity,
                        legal_relation_similarity=item.legal_relation_similarity,
                        dispute_focus_similarity=item.dispute_focus_similarity,
                        judgment_reference_value=item.judgment_reference_value,
                        overall=item.overall,
                    ),
                    analysis=item.analysis,
                )
            )

        results.sort(key=lambda r: r.relevance.overall, reverse=True)
        return results

    def _build_user_prompt(
        self, case_data: dict[str, Any], candidates: list[CaseIndexEntry]
    ) -> str:
        """构建用户提示词。"""
        parts: list[str] = ["## 当前案件信息\n"]

        parties = case_data.get("parties", {})
        for role, info in parties.items():
            name = info.get("name", "")
            if name:
                role_zh = "原告" if "plaintiff" in role else "被告"
                parts.append(f"{role_zh}：{name}")

        for row in case_data.get("summary", []):
            if isinstance(row, list) and len(row) >= 2:
                parts.append(f"{row[0]}：{row[1]}")

        for c in case_data.get("claims", []):
            text = c.get("text", "") if isinstance(c, dict) else str(c)
            if text:
                parts.append(f"诉请：{text}")
        for d in case_data.get("defenses", []):
            text = d.get("text", "") if isinstance(d, dict) else str(d)
            if text:
                parts.append(f"抗辩：{text}")

        parts.append("\n## 候选类案（请以严格 JSON 格式输出评估结果，不要使用 Markdown）\n")
        for i, entry in enumerate(candidates, 1):
            parts.append(
                f"{i}. 案号：{entry.case_number}\n"
                f"   法院：{entry.court}\n"
                f"   案由：{entry.cause_of_action}\n"
                f"   关键词：{', '.join(entry.keywords)}\n"
                f"   摘要：{entry.summary}"
            )

        return "\n".join(parts)
