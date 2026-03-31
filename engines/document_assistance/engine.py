"""
文书辅助引擎主类。
Document assistance engine main class.

职责 / Responsibilities:
1. 根据 (doc_type, case_type) 从 PROMPT_REGISTRY 查找提示函数
2. 调用 call_structured_llm() 获取结构化输出
3. 校验 evidence_ids_cited 非空（强制验收条件）
4. 返回 DocumentDraft

合约保证 / Contract guarantees:
- 所有成功输出的 DocumentDraft.evidence_ids_cited 非空（CrossExaminationOpinion 且 EvidenceIndex 为空时除外）
- LLM 返回不符合 schema 的 JSON → DocumentGenerationError，消息包含 doc_type 和 case_type
- (doc_type, case_type) 不在 PROMPT_REGISTRY → DocumentGenerationError
- EvidenceIndex 为空 + doc_type=cross_exam → 返回 items=[]，不调 LLM，不抛错
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Union

from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .prompts import PROMPT_REGISTRY
from .schemas import (
    CrossExaminationOpinion,
    CrossExaminationOpinionItem,
    DefenseStatement,
    DocumentAssistanceInput,
    DocumentDraft,
    DocumentGenerationError,
    PleadingDraft,
)

# 每种 doc_type 对应的 LLM tool 元数据
_TOOL_META: dict[str, tuple[str, str]] = {
    "pleading": ("generate_pleading_draft", "生成起诉状骨架草稿"),
    "defense": ("generate_defense_statement", "生成答辩状骨架草稿"),
    "cross_exam": ("generate_cross_exam_opinion", "生成质证意见骨架草稿"),
}

# 每种 doc_type 对应的 LLM 输出 JSON Schema
_TOOL_SCHEMAS: dict[str, dict] = {
    "pleading": PleadingDraft.model_json_schema(),
    "defense": DefenseStatement.model_json_schema(),
    "cross_exam": CrossExaminationOpinion.model_json_schema(),
}


def _parse_content(
    doc_type: str,
    data: dict,
) -> Union[PleadingDraft, DefenseStatement, CrossExaminationOpinion]:
    """将 LLM 返回的 dict 解析为对应的文书骨架模型。
    Parse LLM-returned dict into the corresponding document skeleton model.
    """
    if doc_type == "pleading":
        return PleadingDraft.model_validate(data)
    if doc_type == "defense":
        return DefenseStatement.model_validate(data)
    if doc_type == "cross_exam":
        return CrossExaminationOpinion.model_validate(data)
    raise ValueError(f"Unknown doc_type: {doc_type}")  # pragma: no cover


class DocumentAssistanceEngine:
    """文书辅助引擎。

    Args:
        llm_client:  符合 LLMClient 协议的客户端实例
        model:       LLM 模型标识
        temperature: 生成温度（默认 0.0）
        max_retries: LLM 调用失败时的最大重试次数
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries

    async def generate(self, *, input: DocumentAssistanceInput) -> DocumentDraft:
        """生成一份结构化文书草稿。
        Generate a structured document draft.

        Args:
            input: DocumentAssistanceInput — 包含案件上下文和文书类型 / contains case context and doc type

        Returns:
            DocumentDraft — 结构化文书骨架 / structured document skeleton

        Raises:
            DocumentGenerationError: LLM 失败、schema 校验失败或 evidence_ids_cited 为空时抛出 /
                                     raised on LLM failure, schema validation failure,
                                     or empty evidence_ids_cited
        """
        doc_type = input.doc_type
        case_type = input.case_type

        # 校验 (doc_type, case_type) 注册
        key = (doc_type, case_type)
        if key not in PROMPT_REGISTRY:
            raise DocumentGenerationError(
                f"No prompt registered for doc_type={doc_type}, case_type={case_type}"
            )

        # 边界情况：cross_exam + 空证据 → 不调 LLM，直接返回空
        if doc_type == "cross_exam" and not input.evidence_index.evidence:
            content = CrossExaminationOpinion(items=[], evidence_ids_cited=[])
            return DocumentDraft(
                doc_type=doc_type,
                case_type=case_type,
                case_id=input.case_id,
                run_id=input.run_id,
                content=content,
                evidence_ids_cited=[],
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

        # 获取 prompt
        system_prompt, build_user_prompt = PROMPT_REGISTRY[key]
        user_prompt = build_user_prompt(
            issue_tree=input.issue_tree,
            evidence_index=input.evidence_index,
            case_data=input.case_data,
            attack_chain=input.attack_chain,
        )

        # 调用 LLM
        tool_name, tool_desc = _TOOL_META[doc_type]
        tool_schema = _TOOL_SCHEMAS[doc_type]

        try:
            data = await call_structured_llm(
                self._llm,
                system=system_prompt,
                user=user_prompt,
                model=self._model,
                tool_name=tool_name,
                tool_description=tool_desc,
                tool_schema=tool_schema,
                temperature=self._temperature,
                max_retries=self._max_retries,
            )
        except Exception as exc:
            raise DocumentGenerationError(
                f"LLM call failed for doc_type={doc_type}, case_type={case_type}: {exc}"
            ) from exc

        # 解析为对应 schema
        try:
            content = _parse_content(doc_type, data)
        except Exception as exc:
            raise DocumentGenerationError(
                f"Schema validation failed for doc_type={doc_type}, case_type={case_type}: {exc}"
            ) from exc

        # 强制验收条件：evidence_ids_cited 非空
        if not content.evidence_ids_cited:
            raise DocumentGenerationError(
                f"evidence_ids_cited is empty for doc_type={doc_type}, case_type={case_type}; "
                "document drafts must cite at least 1 evidence_id"
            )

        # 对 cross_exam 补充 items 中的 evidence_id（确保覆盖 LLM 可能缺失的条目）
        if doc_type == "cross_exam":
            cited_in_items = {item.evidence_id for item in content.items}
            extra = [eid for eid in content.evidence_ids_cited if eid not in cited_in_items]
            if extra:
                extra_items = [
                    CrossExaminationOpinionItem(
                        evidence_id=eid,
                        opinion_text="（LLM 未生成具体意见，请律师补充）",
                    )
                    for eid in extra
                ]
                content = CrossExaminationOpinion(
                    items=content.items + extra_items,
                    evidence_ids_cited=content.evidence_ids_cited,
                )

        return DocumentDraft(
            doc_type=doc_type,
            case_type=case_type,
            case_id=input.case_id,
            run_id=input.run_id,
            content=content,
            evidence_ids_cited=content.evidence_ids_cited,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
