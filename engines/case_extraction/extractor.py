"""
案件文本提取器核心模块
Case text extractor core module

接受起诉书、案情摘要或裁判文书文本，通过 LLM 结构化提取案件关键信息，
输出兼容 cases/wang_v_chen_zhuang_2025.yaml schema 的 YAML 字符串。

Accepts complaint text, case summaries, or judgment documents,
extracts structured case information via LLM,
and outputs YAML compatible with the cases/ schema.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import yaml

from engines.shared.structured_output import call_structured_llm

from .schemas import (
    CaseExtractionResult,
    DisputedAmount,
    ExtractionClaim,
    ExtractionEvidence,
    ExtractionParty,
    LLMCaseExtractionOutput,
)

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

# tool_use 模式的 JSON Schema，模块加载时计算一次
_TOOL_SCHEMA: dict = LLMCaseExtractionOutput.model_json_schema()

_SYSTEM_PROMPT = """\
你是一名专业的中国民事诉讼案件信息提取助手。
你的任务是从用户提供的法律文本（起诉书、案情摘要或裁判文书）中
提取结构化案件信息，并严格按照工具 schema 输出。

提取规则：
1. 原被告姓名：直接从文中提取，无法确定填 "unknown"
2. 案件类型：civil_loan（民间借贷）、labor_dispute（劳动纠纷）、real_estate（房产纠纷）或 unknown
3. 诉讼请求：按文中顺序提取，每项独立列出
4. 证据：提取文中明确提及的证据，注明提交方和类型
5. 争议金额：提取所有出现的具体金额（纯数字，单位元），若有多个不同值全部列出
6. 若信息不足或无法判断，相应字段填 "unknown"，不要猜测

You are a professional Chinese civil litigation case information extraction assistant.
Extract structured case information from legal text strictly following the tool schema.
"""

_USER_PROMPT_TEMPLATE = """\
请从以下法律文本中提取案件信息：

---
{text}
---

按工具 schema 输出所有可提取字段。无法确定的字段填 "unknown"。
"""


def _dedup_amounts(amounts: list[str]) -> list[str]:
    """去重并保留顺序。Remove duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for a in amounts:
        normalized = re.sub(r"[,，\s]", "", a)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


class CaseExtractor:
    """案件文本提取器
    Case Text Extractor

    从法律文本中提取案件结构化信息，输出兼容 cases/ schema 的 YAML。
    Extracts structured case information from legal text, outputs YAML compatible
    with the cases/ schema.

    Args:
        llm_client: 符合 LLMClient 协议的客户端实例 / LLMClient-compatible instance
        model:       LLM 模型名称 / Model name
        temperature: LLM 温度，结构化提取用 0.0 / Temperature (0.0 for structured output)
        max_tokens:  最大输出 token 数 / Max output tokens
        max_retries: LLM 调用失败最大重试次数 / Max retries on failure
    """

    def __init__(
        self,
        llm_client: "LLMClient",
        *,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> None:
        self._llm_client = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

    async def extract(self, text: str) -> CaseExtractionResult:
        """从文本中提取案件信息。
        Extract case information from text.

        Args:
            text: 起诉书、案情摘要或裁判文书的文本内容。
                  Complaint text, case summary, or judgment document.

        Returns:
            CaseExtractionResult 包含提取的结构化案件信息。
            CaseExtractionResult with structured extracted case info.

        Raises:
            ValueError: 输入文本为空 / Input text is empty
            RuntimeError: LLM 调用失败超过重试次数 / LLM call failed after max retries
        """
        if not text or not text.strip():
            raise ValueError(
                "输入文本不能为空 / Input text cannot be empty. "
                "请提供起诉书、案情摘要或裁判文书内容。"
            )

        user_prompt = _USER_PROMPT_TEMPLATE.format(text=text.strip())

        raw_dict = await call_structured_llm(
            self._llm_client,
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            model=self._model,
            tool_name="extract_case_info",
            tool_description=(
                "从法律文本中提取案件结构化信息：原被告、案件类型、诉讼请求、证据和争议金额。"
                "Extract structured case information from legal text: parties, case type, "
                "claims, evidence, and disputed amounts."
            ),
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )

        llm_output = LLMCaseExtractionOutput.model_validate(raw_dict)
        return self._build_result(llm_output)

    def _build_result(self, llm_output: LLMCaseExtractionOutput) -> CaseExtractionResult:
        """将 LLM 输出组装为 CaseExtractionResult。
        Assemble CaseExtractionResult from LLM output."""
        unknown_fields: list[str] = []

        # ── 原告 / Plaintiff ──────────────────────────────────────────────────
        p_name = llm_output.plaintiff_name or "unknown"
        if p_name == "unknown":
            unknown_fields.append("parties.plaintiff.name")
        plaintiff = ExtractionParty(party_id="party-plaintiff-1", name=p_name)

        # ── 被告 / Defendants ─────────────────────────────────────────────────
        raw_defendants = llm_output.defendant_names or ["unknown"]
        if not raw_defendants:
            raw_defendants = ["unknown"]
        defendants: list[ExtractionParty] = []
        for i, d_name in enumerate(raw_defendants, 1):
            if d_name == "unknown" and i == 1:
                unknown_fields.append("parties.defendant.name")
            defendants.append(ExtractionParty(party_id=f"party-defendant-{i}", name=d_name))

        # ── 案件类型 / Case type ───────────────────────────────────────────────
        case_type = llm_output.case_type or "unknown"
        if case_type == "unknown":
            unknown_fields.append("case_type")

        # ── 诉讼请求 / Claims ─────────────────────────────────────────────────
        claims: list[ExtractionClaim] = []
        for i, c in enumerate(llm_output.claims, 1):
            claims.append(
                ExtractionClaim(
                    claim_id=f"c-{i:03d}",
                    claim_category=c.claim_category,
                    title=c.title,
                    claim_text=c.claim_text,
                )
            )

        # ── 证据 / Evidence ───────────────────────────────────────────────────
        evidence_list: list[ExtractionEvidence] = []
        for i, e in enumerate(llm_output.evidence_list, 1):
            submitter = e.submitter if e.submitter in ("plaintiff", "defendant") else "unknown"
            evidence_list.append(
                ExtractionEvidence(
                    source_id=f"src-extracted-{i:03d}",
                    description=e.description,
                    document_type=e.document_type,
                    submitter=submitter,
                )
            )

        # ── 争议金额 / Disputed amount ────────────────────────────────────────
        deduped = _dedup_amounts(llm_output.disputed_amounts)
        if len(deduped) >= 2:
            disputed_amount = DisputedAmount(amounts=deduped, is_ambiguous=True)
            unknown_fields.append("financials.disputed_amount")
        elif len(deduped) == 1:
            disputed_amount = DisputedAmount(amounts=deduped, is_ambiguous=False)
        else:
            disputed_amount = DisputedAmount(amounts=["unknown"], is_ambiguous=False)
            unknown_fields.append("financials.disputed_amount")

        return CaseExtractionResult(
            case_type=case_type,
            plaintiff=plaintiff,
            defendants=defendants,
            claims=claims,
            evidence_list=evidence_list,
            disputed_amount=disputed_amount,
            case_summary=llm_output.case_summary or "unknown",
            unknown_fields=unknown_fields,
        )

    def to_yaml(self, result: CaseExtractionResult, case_slug: str = "") -> str:
        """将 CaseExtractionResult 序列化为兼容 cases/ schema 的 YAML 字符串。
        Serialize CaseExtractionResult to a YAML string compatible with cases/ schema.

        unknown 字段自动加 # TODO: verify 注释；
        ambiguous 金额加 # ambiguous: multiple values found 注释。

        unknown fields get # TODO: verify comments;
        ambiguous amounts get # ambiguous: multiple values found comments.

        Args:
            result:    CaseExtractionResult 提取结果 / Extraction result
            case_slug: YAML 文件标识符（不含空格），默认根据时间生成。
                       Case identifier (no spaces), defaults to timestamp-based slug.

        Returns:
            YAML 字符串 / YAML string
        """
        now_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        slug = case_slug or f"extracted-{now_date}"
        case_id = f"case-{result.case_type}-{slug}"

        # ── 当事人 / Parties ──────────────────────────────────────────────────
        defendant_primary = (
            result.defendants[0]
            if result.defendants
            else ExtractionParty(party_id="party-defendant-1", name="unknown")
        )
        parties_dict: dict = {
            "plaintiff": {
                "party_id": result.plaintiff.party_id,
                "name": result.plaintiff.name,
            },
            "defendant": {
                "party_id": defendant_primary.party_id,
                "name": defendant_primary.name,
            },
        }

        # ── 证据 → materials ──────────────────────────────────────────────────
        plaintiff_materials = []
        defendant_materials = []
        for ev in result.evidence_list:
            entry = {
                "source_id": ev.source_id,
                "text": ev.description,
                "metadata": {
                    "document_type": ev.document_type,
                    "submitter": ev.submitter,
                    "status": "admitted_for_discussion",
                },
            }
            if ev.submitter == "defendant":
                defendant_materials.append(entry)
            else:
                plaintiff_materials.append(entry)

        # ── 诉讼请求 / Claims ─────────────────────────────────────────────────
        claims_list = [
            {
                "claim_id": c.claim_id,
                "claim_category": c.claim_category,
                "title": c.title,
                "claim_text": c.claim_text,
            }
            for c in result.claims
        ]

        # ── 争议金额 / Financials ─────────────────────────────────────────────
        if result.disputed_amount.is_ambiguous:
            # 多候选值 → disputed 条目标为 ambiguous
            disputed_entries = [
                {"amount": amt, "note": "ambiguous"} for amt in result.disputed_amount.amounts
            ]
            claim_entries_amount = "ambiguous"
        elif result.disputed_amount.amounts and result.disputed_amount.amounts[0] != "unknown":
            disputed_entries = []
            claim_entries_amount = result.disputed_amount.amounts[0]
        else:
            disputed_entries = []
            claim_entries_amount = "unknown"

        claim_entries = []
        if claims_list:
            claim_entries.append(
                {
                    "claim_id": claims_list[0]["claim_id"],
                    "claim_type": "principal",
                    "claimed_amount": claim_entries_amount,
                    "evidence_ids": [],
                }
            )

        structure = {
            "case_id": case_id,
            "case_slug": slug,
            "case_type": result.case_type,
            "model": "claude-sonnet-4-6",
            "parties": parties_dict,
            "summary": [],
            "materials": {
                "plaintiff": plaintiff_materials,
                "defendant": defendant_materials,
            },
            "claims": claims_list,
            "defenses": [],
            "financials": {
                "loans": [],
                "repayments": [],
                "disputed": disputed_entries,
                "claim_entries": claim_entries,
            },
        }

        raw_yaml = yaml.dump(
            structure,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
        )

        return _inject_todo_comments(raw_yaml)


def _inject_todo_comments(yaml_str: str) -> str:
    """在含 unknown/ambiguous 值的行后注入 TODO 注释。
    Inject TODO/ambiguous comments after lines containing unknown/ambiguous values.
    """
    lines = yaml_str.splitlines()
    result = []
    for line in lines:
        # 匹配 YAML 标量值为 'unknown' 或 "unknown" 的行
        if re.search(r":\s+['\"]?unknown['\"]?\s*$", line):
            line = line.rstrip() + "  # TODO: verify"
        # 匹配 disputed 条目中 note: ambiguous
        elif re.search(r":\s+['\"]?ambiguous['\"]?\s*$", line):
            line = line.rstrip() + "  # ambiguous: multiple values found, verify manually"
        result.append(line)
    return "\n".join(result) + "\n"
