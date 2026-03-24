"""
证据索引器核心模块

将原始案件材料转化为结构化 Evidence 对象。
通过 LLM 进行智能提取，支持多案由 prompt 模板。
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, runtime_checkable

from .schemas import (
    AccessDomain,
    Evidence,
    EvidenceIndexResult,
    EvidenceStatus,
    EvidenceType,
    LLMEvidenceItem,
    RawMaterial,
)


@runtime_checkable
class LLMClient(Protocol):
    """LLM 客户端协议 - 兼容 Anthropic 和 OpenAI SDK"""

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
        """发送消息并返回文本响应"""
        ...


# 证据类型映射：中文 ↔ 英文 ↔ EvidenceType 枚举
_EVIDENCE_TYPE_MAP: dict[str, EvidenceType] = {
    "书证": EvidenceType.DOCUMENTARY,
    "documentary": EvidenceType.DOCUMENTARY,
    "物证": EvidenceType.PHYSICAL,
    "physical": EvidenceType.PHYSICAL,
    "电子数据": EvidenceType.ELECTRONIC,
    "electronic": EvidenceType.ELECTRONIC,
    "证人证言": EvidenceType.WITNESS,
    "witness": EvidenceType.WITNESS,
    "当事人陈述": EvidenceType.PARTY_STATEMENT,
    "party_statement": EvidenceType.PARTY_STATEMENT,
    "鉴定意见": EvidenceType.EXPERT_OPINION,
    "expert_opinion": EvidenceType.EXPERT_OPINION,
    "勘验笔录": EvidenceType.INSPECTION,
    "inspection": EvidenceType.INSPECTION,
}


def _resolve_evidence_type(raw_type: str) -> EvidenceType:
    """将 LLM 返回的证据类型字符串解析为枚举值

    使用精确匹配而非模糊子串匹配，避免误分类。
    """
    normalized = raw_type.strip().lower()
    # 精确匹配
    if normalized in _EVIDENCE_TYPE_MAP:
        return _EVIDENCE_TYPE_MAP[normalized]
    # 尝试去除空格后匹配
    no_space = normalized.replace(" ", "").replace("_", "")
    for key, value in _EVIDENCE_TYPE_MAP.items():
        if key.replace("_", "") == no_space:
            return value
    # 未知类型返回默认值
    return EvidenceType.DOCUMENTARY


def _extract_json_array(text: str) -> list[dict]:
    """从 LLM 响应中提取 JSON 数组

    支持：纯 JSON、markdown 代码块包裹、前后有额外文字。
    """
    # 尝试提取 markdown 代码块中的 JSON
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

    # 尝试直接解析整个文本
    try:
        result = json.loads(text.strip())
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # 尝试提取方括号包裹的内容
    bracket_pattern = r"\[[\s\S]*\]"
    match = re.search(bracket_pattern, text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 响应中提取 JSON 数组: {text[:200]}...")


class EvidenceIndexer:
    """证据索引器

    将原始案件材料通过 LLM 提取为结构化 Evidence 对象。

    Args:
        llm_client: 符合 LLMClient 协议的客户端实例
        case_type: 案由类型，用于选择 prompt 模板，默认 "civil_loan"
        model: LLM 模型名称
        temperature: LLM 温度参数，结构化提取建议用 0.0
        max_tokens: LLM 最大输出 token 数
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

        使用注册表模式，支持动态扩展新案由。
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
        """验证输入材料

        Raises:
            ValueError: 输入为空或有重复 source_id
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
        case_slug: str = "case",
    ) -> EvidenceIndexResult:
        """执行证据索引

        Args:
            materials: 原始案件材料列表
            case_id: 案件 ID
            case_slug: 案件简称，用于生成 evidence_id

        Returns:
            EvidenceIndexResult 包含结构化 Evidence 对象列表

        Raises:
            ValueError: 输入无效或 LLM 响应无法解析
            RuntimeError: LLM 调用失败且超过最大重试次数
        """
        self._validate_input(materials)

        # 构建 prompt
        system_prompt = self._prompt_module.SYSTEM_PROMPT
        materials_block = self._prompt_module.format_materials_block(materials)
        user_prompt = self._prompt_module.EXTRACTION_PROMPT.format(
            materials=materials_block
        )

        # 调用 LLM（带重试）
        raw_response = await self._call_llm_with_retry(system_prompt, user_prompt)

        # 解析 LLM 输出
        raw_items = _extract_json_array(raw_response)

        # 构建 Evidence 对象
        evidences = self._build_evidences(raw_items, case_id, case_slug, materials)

        return EvidenceIndexResult(
            case_id=case_id,
            evidence=evidences,
            extraction_metadata={
                "total_materials_processed": len(materials),
                "total_evidence_extracted": len(evidences),
                "case_type": self._case_type,
                "model": self._model,
            },
        )

    async def _call_llm_with_retry(
        self, system: str, user: str
    ) -> str:
        """调用 LLM 并在失败时重试

        Args:
            system: 系统提示词
            user: 用户消息

        Returns:
            LLM 的文本响应

        Raises:
            RuntimeError: 超过最大重试次数
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
                    continue  # 重试
                break

        raise RuntimeError(
            f"LLM 调用失败，已重试 {self._max_retries} 次。"
            f"最后一次错误: {last_error}"
        )

    def _build_evidences(
        self,
        raw_items: list[dict],
        case_id: str,
        case_slug: str,
        materials: list[RawMaterial],
    ) -> list[Evidence]:
        """将 LLM 提取的原始项转化为 Evidence 对象

        强制执行合约不变量：
        - status = private
        - access_domain = owner_private
        - 每条证据至少一个 target_fact_id
        - evidence_id 全局唯一
        """
        # 构建 source_id → material 映射
        material_map = {m.source_id: m for m in materials}

        evidences: list[Evidence] = []
        seen_ids: set[str] = set()

        for idx, raw in enumerate(raw_items, start=1):
            # 解析 LLM 输出为中间模型
            try:
                llm_item = LLMEvidenceItem.model_validate(raw)
            except Exception:
                continue  # 跳过无法解析的项

            # 生成唯一 ID
            evidence_id = f"evidence-{case_slug}-{idx:03d}"
            while evidence_id in seen_ids:
                idx += 1
                evidence_id = f"evidence-{case_slug}-{idx:03d}"
            seen_ids.add(evidence_id)

            # 解析证据类型
            evidence_type = _resolve_evidence_type(llm_item.evidence_type)

            # 确保至少一个 target_fact_id
            target_fact_ids = llm_item.target_facts or []
            if not target_fact_ids:
                target_fact_ids = [f"fact-{case_slug}-{idx:03d}-unknown"]

            # 查找来源材料的 owner
            source_material = material_map.get(llm_item.source_id or "")
            owner_party_id = None
            if source_material and source_material.metadata:
                owner_party_id = source_material.metadata.get("owner_party_id")

            evidence = Evidence(
                evidence_id=evidence_id,
                case_id=case_id,
                owner_party_id=owner_party_id,
                title=llm_item.title,
                source=llm_item.source_id or f"material-{idx}",
                summary=llm_item.summary,
                evidence_type=evidence_type.value,
                target_fact_ids=target_fact_ids,
                target_issue_ids=llm_item.target_issue_ids or [],
                access_domain=AccessDomain.OWNER_PRIVATE.value,
                status=EvidenceStatus.PRIVATE.value,
                submitted_by_party_id=None,
                challenged_by_party_ids=[],
                admissibility_notes=None,
            )
            evidences.append(evidence)

        return evidences