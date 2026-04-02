"""
关键词提取器 — 用 LLM 从案件数据提取搜索关键词。
Keyword extractor — uses LLM to extract search keywords from case data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

from engines.shared.structured_output import call_structured_llm
from .schemas import CaseKeywords, LLMKeywordsOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一名资深中国法律检索专家。根据提供的案件信息，提取适合在人民法院案例库中搜索类案的关键词。

要求：
1. 准确识别案由（如：民间借贷纠纷、买卖合同纠纷等）
2. 提取核心法律关系
3. 识别主要争议焦点
4. 列出相关法条
5. 生成 3-8 个搜索关键词，覆盖案由、核心事实、法律要点

你必须以严格 JSON 格式输出，不得包含任何 Markdown 标记、代码块或其他非 JSON 内容。
输出格式示例：
{
  "cause_of_action": "民间借贷纠纷",
  "legal_relations": ["借贷关系", "担保关系"],
  "dispute_focuses": ["借款合意是否成立", "还款金额争议"],
  "relevant_statutes": ["《民法典》第六百七十五条"],
  "search_terms": ["民间借贷", "借条", "还款期限"]
}
"""

_TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "cause_of_action": {"type": "string", "description": "案由（如：民间借贷纠纷）"},
        "legal_relations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "核心法律关系列表",
        },
        "dispute_focuses": {
            "type": "array",
            "items": {"type": "string"},
            "description": "主要争议焦点列表",
        },
        "relevant_statutes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "相关法条列表",
        },
        "search_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "搜索关键词列表（3-8个）",
        },
    },
    "required": [
        "cause_of_action",
        "legal_relations",
        "dispute_focuses",
        "relevant_statutes",
        "search_terms",
    ],
}


class KeywordExtractor:
    """从案件数据中提取类案搜索关键词。"""

    def __init__(
        self,
        llm_client: "LLMClient",
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

    async def extract(self, case_data: dict[str, Any]) -> CaseKeywords:
        """从案件数据提取搜索关键词。"""
        user_prompt = self._build_user_prompt(case_data)
        logger.info("提取类案搜索关键词...")

        data = await call_structured_llm(
            self._llm,
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            model=self._model,
            tool_name="extract_case_keywords",
            tool_description="从案件信息中提取类案搜索关键词",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )

        output = LLMKeywordsOutput.model_validate(data)
        return CaseKeywords(
            cause_of_action=output.cause_of_action,
            legal_relations=output.legal_relations,
            dispute_focuses=output.dispute_focuses,
            relevant_statutes=output.relevant_statutes,
            search_terms=output.search_terms,
        )

    def _build_user_prompt(self, case_data: dict[str, Any]) -> str:
        """构建用户提示词，包含案件核心信息。"""
        parts: list[str] = []

        parties = case_data.get("parties", {})
        for role, info in parties.items():
            name = info.get("name", "")
            if name:
                role_zh = "原告" if "plaintiff" in role else "被告"
                parts.append(f"{role_zh}：{name}")

        for row in case_data.get("summary", []):
            if isinstance(row, list) and len(row) >= 2:
                parts.append(f"{row[0]}：{row[1]}")

        claims = case_data.get("claims", [])
        if claims:
            parts.append("诉讼请求：")
            for c in claims:
                text = c.get("text", "") if isinstance(c, dict) else str(c)
                if text:
                    parts.append(f"  - {text}")

        defenses = case_data.get("defenses", [])
        if defenses:
            parts.append("被告抗辩：")
            for d in defenses:
                text = d.get("text", "") if isinstance(d, dict) else str(d)
                if text:
                    parts.append(f"  - {text}")

        case_type = case_data.get("case_type", "")
        if case_type:
            parts.append(f"案件类型：{case_type}")

        return "\n".join(parts)
