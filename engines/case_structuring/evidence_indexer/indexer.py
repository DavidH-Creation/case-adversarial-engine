"""
证据索引器核心模块
Evidence Indexer core module.

将原始案件材料转化为结构化 Evidence 对象。
Transforms raw case materials into structured Evidence objects via LLM.
通过 LLM 进行智能提取，支持多案由 prompt 模板。
Supports multi-case-type prompt templates.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, runtime_checkable

from .schemas import (
    AccessDomain,
    Evidence,
    EvidenceStatus,
    EvidenceType,
    LLMEvidenceItem,
    RawMaterial,
)


@runtime_checkable
class LLMClient(Protocol):
    """LLM 客户端协议 - 兼容 Anthropic 和 OpenAI SDK
    LLM client protocol - compatible with Anthropic and OpenAI SDKs.
    """

    async def create_message(
        self,
        *,
        system: str,
        user: str,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """发送消息并返回文本响应 / Send message and return text response."""
        ...


# 证据类型映射：中文 ↔ 英文 ↔ EvidenceType 枚举
# Evidence type mapping: Chinese ↔ English ↔ EvidenceType enum
_EVIDENCE_TYPE_MAP: dict[str, EvidenceType] = {
    "书证": EvidenceType.documentary,
    "documentary": EvidenceType.documentary,
    "物证": EvidenceType.physical,
    "physical": EvidenceType.physical,
    "电子数据": EvidenceType.electronic_data,
    "electronic_data": EvidenceType.electronic_data,
    "electronic": EvidenceType.electronic_data,
    "证人证言": EvidenceType.witness_statement,
    "witness_statement": EvidenceType.witness_statement,
    "witness": EvidenceType.witness_statement,
    "鉴定意见": EvidenceType.expert_opinion,
    "expert_opinion": EvidenceType.expert_opinion,
    "视听资料": EvidenceType.audio_visual,
    "audio_visual": EvidenceType.audio_visual,
    # 以下类型在 schema 中无对应枚举值，映射到 other
    # Types below have no direct enum value, map to other
    "当事人陈述": EvidenceType.other,
    "party_statement": EvidenceType.other,
    "勘验笔录": EvidenceType.other,
    "inspection": EvidenceType.other,
}


def _resolve_evidence_type(raw_type: str) -> EvidenceType:
    """将 LLM 返回的证据类型字符串解析为枚举值
    Map LLM-returned evidence type string to enum value.

    使用精确匹配，避免误分类；未知类型返回 other。
    Uses exact matching to avoid misclassification; unknown types return other.
    """
    normalized = raw_type.strip().lower()
    # 精确匹配 / Exact match
    if normalized in _EVIDENCE_TYPE_MAP:
        return _EVIDENCE_TYPE_MAP[normalized]
    # 去除空格和下划线后匹配 / Match after removing spaces and underscores
    no_sep = normalized.replace(" ", "").replace("_", "")
    for key, value in _EVIDENCE_TYPE_MAP.items():
        if key.replace("_", "") == no_sep:
            return value
    # 未知类型返回 other / Unknown type defaults to other
    return EvidenceType.other


def _extract_json_array(text: str) -> list[dict]:
    """从 LLM 响应中提取 JSON 数组
    Extract JSON array from LLM response.

    支持：纯 JSON、markdown 代码块包裹、前后有额外文字。
    Supports: plain JSON, markdown code block, text with surrounding content.
    """
    # 尝试提取 markdown 代码块中的 JSON / Try extracting from markdown code block
    code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```"
    match = re.search(code_block_pattern, text)
    if match:
        candidate = match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # 尝试直接解析整个文本 / Try parsing entire text directly
    try:
        result = json.loads(text.strip())
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # 尝试提取方括号包裹的内容 / Try extracting bracket-wrapped content
    bracket_pattern = r"\[[\s\S]*\]"
    match = re.search(bracket_pattern, text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 响应中解析 JSON 数组: {text[:200]}")


class EvidenceIndexer:
    """证据索引器
    Evidence Indexer.

    将原始案件材料通过 LLM 提取为结构化 Evidence 对象。
    Extracts structured Evidence objects from raw case materials via LLM.

    Args:
        llm_client: 符合 LLMClient 协议的客户端实例 / LLMClient-protocol-compliant instance
        case_type: 案由类型，用于选择 prompt 模板，默认 "civil_loan"
                   Case type for selecting prompt template, default "civil_loan"
        model: LLM 模型名称 / LLM model name
        temperature: LLM 温度参数，结构化提取建议用 0.0
                     LLM temperature; 0.0 recommended for structured extraction
        max_tokens: LLM 最大输出 token 数 / Max output tokens
        max_retries: LLM 调用失败时的最大重试次数 / Max retries on LLM failure
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
        self._llm_client = llm_client
        self._case_type = case_type
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._prompt_module = self._load_prompt_module(case_type)

    @staticmethod
    def _load_prompt_module(case_type: str):
        """加载案由对应的 prompt 模板模块
        Load prompt template module for the given case type.

        使用注册表模式，支持动态扩展新案由。
        Registry pattern supports dynamically adding new case types.
        """
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"不支持的案由类型: {case_type}。"
                f"可用类型: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    def _validate_input(self, materials: list[RawMaterial]) -> None:
        """验证输入材料 / Validate input materials.

        Raises:
            ValueError: 输入为空或有重复 source_id / Empty input or duplicate source_ids.
        """
        if not materials:
            raise ValueError("输入材料列表不能为空")

        source_ids = [m.source_id for m in materials]
        duplicates = {sid for sid in source_ids if source_ids.count(sid) > 1}
        if duplicates:
            raise ValueError(f"存在重复的 source_id: {duplicates}")

    async def index(
        self,
        materials: list[RawMaterial],
        case_id: str,
        owner_party_id: str,
        case_slug: str = "case",
    ) -> list[Evidence]:
        """执行证据索引 / Execute evidence indexing.

        Args:
            materials: 原始案件材料列表 / List of raw case materials
            case_id: 案件 ID / Case ID
            owner_party_id: 证据所有方 party_id / Evidence owner party ID
            case_slug: 案件简称，用于生成 evidence_id / Case slug for evidence_id generation

        Returns:
            结构化 Evidence 对象列表 / List of structured Evidence objects

        Raises:
            ValueError: 输入无效或 LLM 响应无法解析 / Invalid input or unparseable LLM response
            RuntimeError: LLM 调用失败且超过最大重试次数 / LLM call failed after max retries
        """
        self._validate_input(materials)

        # 构建 prompt / Build prompt
        system_prompt = self._prompt_module.SYSTEM_PROMPT
        materials_block = self._prompt_module.format_materials_block(materials)
        user_prompt = self._prompt_module.EXTRACTION_PROMPT.format(
            case_id=case_id,
            materials=materials_block,
        )

        # 调用 LLM（带重试）/ Call LLM with retry
        raw_response = await self._call_llm_with_retry(system_prompt, user_prompt)

        # 解析 LLM 输出 / Parse LLM output
        raw_items = _extract_json_array(raw_response)

        # 构建 Evidence 对象 / Build Evidence objects
        return self._build_evidences(raw_items, case_id, owner_party_id, case_slug)

    async def _call_llm_with_retry(
        self, system: str, user: str
    ) -> str:
        """调用 LLM 并在失败时重试 / Call LLM with retry on failure.

        Args:
            system: 系统提示词 / System prompt
            user: 用户消息 / User message

        Returns:
            LLM 的文本响应 / LLM text response

        Raises:
            RuntimeError: 超过最大重试次数 / Exceeded max retries
        """
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._llm_client.create_message(
                    system=system,
                    user=user,
                    model=self._model,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
                return response
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    continue  # 重试 / retry
                break

        raise RuntimeError(
            f"LLM 调用失败，已重试 {self._max_retries} 次。"
            f"最后一次错误: {last_error}"
        )

    def _build_evidences(
        self,
        raw_items: list[dict],
        case_id: str,
        owner_party_id: str,
        case_slug: str,
    ) -> list[Evidence]:
        """将 LLM 提取的原始项转化为 Evidence 对象
        Convert LLM-extracted raw items into Evidence objects.

        强制执行合约不变量 / Enforces contract invariants:
        - status = private
        - access_domain = owner_private
        - 每条证据至少一个 target_fact_id / At least one target_fact_id per evidence
        - evidence_id 全局唯一 / Globally unique evidence_ids
        """
        evidences: list[Evidence] = []
        seen_ids: set[str] = set()

        for idx, raw in enumerate(raw_items, start=1):
            # 解析 LLM 输出为中间模型 / Parse LLM output to intermediate model
            try:
                llm_item = LLMEvidenceItem.model_validate(raw)
            except Exception:
                continue  # 跳过无法解析的项 / skip unparseable items

            # 生成唯一 ID / Generate unique ID
            evidence_id = f"evidence-{case_slug}-{idx:03d}"
            while evidence_id in seen_ids:
                idx += 1
                evidence_id = f"evidence-{case_slug}-{idx:03d}"
            seen_ids.add(evidence_id)

            # 解析证据类型 / Resolve evidence type
            evidence_type = _resolve_evidence_type(llm_item.evidence_type)

            # 确保至少一个 target_fact_id / Ensure at least one target_fact_id
            target_fact_ids = llm_item.target_facts or []
            if not target_fact_ids:
                target_fact_ids = [f"fact-{case_slug}-{idx:03d}-unknown"]

            evidence = Evidence(
                evidence_id=evidence_id,
                case_id=case_id,
                owner_party_id=owner_party_id,
                title=llm_item.title,
                source=llm_item.source_id or f"material-{idx}",
                summary=llm_item.summary,
                evidence_type=evidence_type,
                target_fact_ids=target_fact_ids,
                target_issue_ids=llm_item.target_issues,
                access_domain=AccessDomain.owner_private,
                status=EvidenceStatus.private,
                submitted_by_party_id=None,
                challenged_by_party_ids=[],
                admissibility_notes=None,
            )
            evidences.append(evidence)

        return evidences
