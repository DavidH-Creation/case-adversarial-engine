"""
证据索引器核心模块
Evidence Indexer core module.

将原始案件材料转化为结构化 Evidence 对象。
Transforms raw case materials into structured Evidence objects via LLM.
通过 LLM 进行智能提取，支持多案由 prompt 模板。
Supports multi-case-type prompt templates.
"""

from __future__ import annotations

from engines.shared.json_utils import _extract_json_array
from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .schemas import (
    AccessDomain,
    Evidence,
    EvidenceStatus,
    EvidenceType,
    LLMEvidenceItem,
    RawMaterial,
)

# tool_use 模式：将证据列表包装在对象内（Anthropic tool_use 要求顶层为 object）
# tool_use mode: wrap evidence list inside an object (Anthropic tool_use requires top-level object)
_TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "evidence_items": {
            "type": "array",
            "description": "从案件材料中提取的证据列表 / List of evidence items extracted from case materials",
            "items": LLMEvidenceItem.model_json_schema(),
        }
    },
    "required": ["evidence_items"],
}


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
            raise ValueError(f"不支持的案由类型: {case_type}。可用类型: {available}")
        return PROMPT_REGISTRY[case_type]

    def _validate_input(self, materials: list[RawMaterial]) -> None:
        """验证输入材料 / Validate input materials.

        Raises:
            ValueError: 输入为空或有重复 source_id / Empty input or duplicate source_ids.
        """
        if not materials:
            raise ValueError("输入材料列表不能为空")

        seen_sids: set[str] = set()
        duplicates: set[str] = set()
        for m in materials:
            if m.source_id in seen_sids:
                duplicates.add(m.source_id)
            seen_sids.add(m.source_id)
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
        from .prompts import plugin

        system_prompt = self._prompt_module.SYSTEM_PROMPT
        user_prompt = plugin.get_prompt(
            "evidence_indexer",
            self._case_type,
            {"case_id": case_id, "materials": materials},
        )

        # 调用 LLM（结构化输出优先，fallback 到 json_utils）
        # Call LLM (structured output first, fallback to json_utils)
        raw_items = await self._call_llm_structured(system_prompt, user_prompt)

        # 构建 Evidence 对象 / Build Evidence objects
        evidences = self._build_evidences(raw_items, case_id, owner_party_id, case_slug)

        # source_coverage 校验：每个输入 source_id 至少映射到一条 Evidence
        # Source coverage: every input source_id must map to at least one Evidence
        covered_sources = {e.source for e in evidences}
        uncovered = {m.source_id for m in materials} - covered_sources
        if uncovered:
            raise ValueError(
                f"source_coverage 校验失败：以下 source_id 未映射到任何 Evidence: {uncovered}"
                f" / source_coverage validation failed: no Evidence produced for: {uncovered}"
            )

        return evidences

    async def _call_llm_structured(self, system: str, user: str) -> list[dict]:
        """调用 LLM 并返回证据条目列表（结构化输出优先，fallback 到 json_utils）。
        Call LLM and return list of evidence items (structured output first, fallback to json_utils).

        主路径（AnthropicSDKClient）：使用 tool_use，返回包装对象中的 evidence_items 列表。
        Primary path (AnthropicSDKClient): uses tool_use, returns evidence_items from wrapped object.

        Fallback 路径（其他客户端）：LLM 返回 JSON 数组，由 _extract_json_array 解析。
        Fallback path (other clients): LLM returns JSON array, parsed by _extract_json_array.

        Raises:
            RuntimeError: 超过最大重试次数 / Exceeded max retries
            ValueError:   响应无法解析 / Response cannot be parsed
        """
        # AnthropicSDKClient 支持 tool_use：使用包装 schema，返回 {"evidence_items": [...]}
        # AnthropicSDKClient supports tool_use: use wrapped schema, returns {"evidence_items": [...]}
        if getattr(self._llm_client, "_supports_structured_output", False):
            data = await call_structured_llm(
                self._llm_client,
                system=system,
                user=user,
                model=self._model,
                tool_name="index_evidence",
                tool_description="从案件材料中提取结构化证据条目列表。"
                "Extract a list of structured evidence items from case materials.",
                tool_schema=_TOOL_SCHEMA,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                max_retries=self._max_retries,
            )
            return data.get("evidence_items", [])

        # Fallback：LLM 返回裸 JSON 数组，由 _extract_json_array 解析
        # Fallback: LLM returns a bare JSON array, parsed by _extract_json_array
        from engines.shared.llm_utils import call_llm_with_retry

        raw = await call_llm_with_retry(
            self._llm_client,
            system=system,
            user=user,
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )
        return _extract_json_array(raw)

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
            # 原子批处理：任一项解析失败则整批失败
            # Atomic batch: any parse failure aborts the entire batch
            try:
                llm_item = LLMEvidenceItem.model_validate(raw)
            except Exception as exc:
                raise ValueError(
                    f"批处理失败：第 {idx} 项（索引 {idx - 1}）解析错误，整批中止。"
                    f" / Batch processing failed: item {idx} (index {idx - 1}) parse error, "
                    f"entire batch aborted. Detail: {exc}"
                ) from exc

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
