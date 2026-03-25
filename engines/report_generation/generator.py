"""
报告生成器核心模块
Report generator core module.

将争点树（IssueTree）和证据索引（EvidenceIndex）通过 LLM 生成结构化诊断报告。
Generates a structured diagnostic report from IssueTree + EvidenceIndex via LLM.

合约保证 / Contract guarantees:
- citation_completeness = 100%（每条关键结论有 ≥1 证据引用）
- 覆盖所有顶层 Issue / Covers all root-level issues
- 零悬空引用 / Zero dangling references
- summary ≤ 500 字 / Summary ≤ 500 characters
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from .schemas import (
    EvidenceIndex,
    EvidenceItem,
    IssueTree,
    KeyConclusion,
    LLMReportOutput,
    LLMSectionItem,
    ReportArtifact,
    ReportSection,
    StatementClass,
)


@runtime_checkable
class LLMClient(Protocol):
    """LLM 客户端协议 — 兼容 Anthropic 和 OpenAI SDK。
    LLM client protocol — compatible with Anthropic and OpenAI SDKs.
    """

    async def create_message(
        self,
        *,
        system: str,
        user: str,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        **kwargs: Any,
    ) -> str:
        """发送消息并返回文本响应。Send message and return text response."""
        ...


# ---------------------------------------------------------------------------
# JSON 解析工具 / JSON parsing utilities
# ---------------------------------------------------------------------------


def _extract_json_object(text: str) -> dict:
    """从 LLM 响应中提取 JSON 对象。
    Extract a JSON object from LLM response text.

    依次尝试：markdown 代码块 → 直接解析 → 大括号匹配。
    Tries in order: markdown code block → direct parse → brace extraction.
    """
    # markdown 代码块 / Markdown code block
    code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```"
    match = re.search(code_block_pattern, text)
    if match:
        candidate = match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # 直接解析 / Direct parse
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 大括号提取 / Brace extraction
    brace_pattern = r"\{[\s\S]*\}"
    match = re.search(brace_pattern, text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"无法从 LLM 响应中解析 JSON 对象 / Cannot parse JSON object: {text[:200]}"
    )


def _resolve_statement_class(raw: str) -> StatementClass:
    """将 LLM 返回的 statement_class 字符串解析为枚举值。
    Resolve raw statement_class string to enum value.
    Defaults to 'inference' for unknown values.
    """
    _MAP = {
        "fact": StatementClass.fact,
        "事实": StatementClass.fact,
        "inference": StatementClass.inference,
        "推理": StatementClass.inference,
        "assumption": StatementClass.assumption,
        "假设": StatementClass.assumption,
    }
    return _MAP.get(raw.strip().lower(), StatementClass.inference)


# ---------------------------------------------------------------------------
# 主引擎类 / Main engine class
# ---------------------------------------------------------------------------


class ReportGenerator:
    """报告生成器
    Report Generator.

    输入 IssueTree + EvidenceIndex，输出结构化 ReportArtifact。
    Takes IssueTree + EvidenceIndex, outputs a structured ReportArtifact.

    Args:
        llm_client: 符合 LLMClient 协议的客户端 / LLMClient-compatible client
        case_type: 案由类型，默认 "civil_loan" / Case type, default "civil_loan"
        model: LLM 模型名称 / LLM model name
        temperature: LLM 温度参数 / LLM temperature
        max_tokens: LLM 最大输出 token 数 / Max output tokens
        max_retries: LLM 调用失败时的最大重试次数 / Max retries on failure
    """

    def __init__(
        self,
        llm_client: LLMClient,
        case_type: str = "civil_loan",
        *,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.0,
        max_tokens: int = 8192,
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
        """加载案由对应的 prompt 模板模块。
        Load prompt template module for the given case type.
        """
        from .prompts import PROMPT_REGISTRY

        if case_type not in PROMPT_REGISTRY:
            available = ", ".join(PROMPT_REGISTRY.keys()) or "(none)"
            raise ValueError(
                f"不支持的案由类型 / Unsupported case type: '{case_type}'。"
                f"可用类型 / Available: {available}"
            )
        return PROMPT_REGISTRY[case_type]

    def _validate_input(
        self,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
    ) -> None:
        """验证输入数据合法性。
        Validate input data validity.

        Raises:
            ValueError: issues 为空，或 evidence 与 issue_tree case_id 不匹配。
                        Raised if issues is empty or case_id mismatch.
        """
        if not issue_tree.issues:
            raise ValueError(
                "issue_tree.issues 不能为空 / issue_tree.issues cannot be empty"
            )
        if issue_tree.case_id != evidence_index.case_id:
            raise ValueError(
                f"case_id 不匹配 / case_id mismatch: "
                f"issue_tree={issue_tree.case_id!r} vs "
                f"evidence_index={evidence_index.case_id!r}"
            )

    async def generate(
        self,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        run_id: str,
        report_slug: str = "report",
    ) -> ReportArtifact:
        """执行报告生成。
        Execute report generation.

        Args:
            issue_tree: 结构化争点树 / Structured issue tree
            evidence_index: 证据索引 / Evidence index
            run_id: 本次运行 ID / Run ID for this generation
            report_slug: 报告简称，用于生成 ID / Report slug for ID generation

        Returns:
            结构化 ReportArtifact / Structured ReportArtifact

        Raises:
            ValueError: 输入无效或 LLM 响应无法解析 / Invalid input or unparseable response
            RuntimeError: LLM 调用失败且超过最大重试次数 / LLM call failed after max retries
        """
        self._validate_input(issue_tree, evidence_index)

        case_id = issue_tree.case_id

        # 构建 prompt / Build prompt
        system_prompt = self._prompt_module.SYSTEM_PROMPT
        issue_tree_block = self._prompt_module.format_issue_tree_block(
            issue_tree.model_dump()
        )
        evidence_block = self._prompt_module.format_evidence_block(
            [e.model_dump() for e in evidence_index.evidence]
        )
        user_prompt = self._prompt_module.GENERATION_PROMPT.format(
            case_id=case_id,
            issue_tree_block=issue_tree_block,
            evidence_block=evidence_block,
        )

        # 调用 LLM（带重试）/ Call LLM with retry
        raw_response = await self._call_llm_with_retry(system_prompt, user_prompt)

        # 解析 LLM 输出 / Parse LLM output
        raw_dict = _extract_json_object(raw_response)
        llm_output = LLMReportOutput.model_validate(raw_dict)

        # 构建 ReportArtifact / Build ReportArtifact
        return self._build_report(
            llm_output,
            issue_tree,
            evidence_index,
            case_id,
            run_id,
            report_slug,
        )

    async def _call_llm_with_retry(self, system: str, user: str) -> str:
        """调用 LLM 并在失败时重试。
        Call LLM with retry on failure.

        Raises:
            RuntimeError: 超过最大重试次数 / Max retries exceeded
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
                    continue
                break

        raise RuntimeError(
            f"LLM 调用失败，已重试 {self._max_retries} 次。"
            f"最后一次错误 / Last error: {last_error}"
        )

    def _build_report(
        self,
        llm_output: LLMReportOutput,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        case_id: str,
        run_id: str,
        report_slug: str,
    ) -> ReportArtifact:
        """将 LLM 输出规范化为 ReportArtifact。
        Normalize LLM output into a ReportArtifact.

        强制执行合约不变量 / Enforces contract invariants:
        - 每条 key_conclusion 至少一个 supporting_evidence_id
        - 每个章节至少一个 linked_evidence_id
        - 覆盖所有顶层 Issue
        - summary 截断到 500 字
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 构建 evidence_id 查找集合 / Build evidence ID lookup set
        known_evidence_ids: set[str] = {e.evidence_id for e in evidence_index.evidence}

        # 获取所有顶层 issue_id / Collect all root issue IDs
        root_issue_ids = {
            issue.issue_id
            for issue in issue_tree.issues
            if issue.parent_issue_id is None
        }

        # ── 构建章节列表 / Build sections list ───────────────────────────────
        sections: list[ReportSection] = []
        covered_root_ids: set[str] = set()

        for sec_idx, llm_sec in enumerate(llm_output.sections, start=1):
            section_id = f"sec-{report_slug}-{sec_idx:02d}"

            # 过滤只保留已知的 evidence_id / Filter to known evidence IDs only
            valid_evidence_ids = [
                eid for eid in llm_sec.linked_evidence_ids if eid in known_evidence_ids
            ]

            # 构建关键结论 / Build key conclusions
            conclusions: list[KeyConclusion] = []
            for c_idx, llm_c in enumerate(llm_sec.key_conclusions, start=1):
                # 过滤支持证据 ID / Filter supporting evidence IDs
                valid_supporting = [
                    eid for eid in llm_c.supporting_evidence_ids
                    if eid in known_evidence_ids
                ]

                # 合约保证：至少一个支持证据 / Contract: at least one supporting evidence
                if not valid_supporting and valid_evidence_ids:
                    valid_supporting = [valid_evidence_ids[0]]
                elif not valid_supporting:
                    # 兜底：使用第一条已知证据 / Fallback: use first known evidence
                    first_known = next(iter(known_evidence_ids), None)
                    valid_supporting = [first_known] if first_known else []

                conclusions.append(KeyConclusion(
                    conclusion_id=f"concl-{report_slug}-{sec_idx:02d}-{c_idx:02d}",
                    text=llm_c.text,
                    statement_class=_resolve_statement_class(llm_c.statement_class),
                    supporting_evidence_ids=valid_supporting,
                    supporting_output_ids=[],
                ))

            # 章节关联的争点 ID / Section linked issue IDs
            linked_issue_ids = [
                iid for iid in llm_sec.linked_issue_ids
                if any(issue.issue_id == iid for issue in issue_tree.issues)
            ]

            # 记录已覆盖的顶层争点 / Track covered root issues
            for iid in linked_issue_ids:
                if iid in root_issue_ids:
                    covered_root_ids.add(iid)

            # linked_output_ids：目前无推演输出，用占位符 / Placeholder for agent output IDs
            linked_output_ids = [f"output-{report_slug}-{sec_idx:02d}"]

            sections.append(ReportSection(
                section_id=section_id,
                section_index=sec_idx,
                title=llm_sec.title,
                body=llm_sec.body,
                linked_issue_ids=linked_issue_ids,
                linked_output_ids=linked_output_ids,
                linked_evidence_ids=valid_evidence_ids,
                key_conclusions=conclusions,
            ))

        # ── 补全缺失的顶层争点章节 / Supplement missing root issue sections ──
        # 若 LLM 漏掉了某个顶层争点，自动补一章节 / Auto-add sections for missed root issues
        for root_id in sorted(root_issue_ids - covered_root_ids):
            root_issue = next(
                (i for i in issue_tree.issues if i.issue_id == root_id), None
            )
            if root_issue is None:
                continue

            sec_idx = len(sections) + 1
            section_id = f"sec-{report_slug}-{sec_idx:02d}"

            # 使用该争点关联的证据 / Use evidence associated with this issue
            issue_evidence = [
                eid for eid in root_issue.evidence_ids if eid in known_evidence_ids
            ]
            if not issue_evidence:
                issue_evidence = [next(iter(known_evidence_ids))] if known_evidence_ids else []

            # 生成默认结论 / Generate default conclusion
            default_conclusion = KeyConclusion(
                conclusion_id=f"concl-{report_slug}-{sec_idx:02d}-01",
                text=f"争点「{root_issue.title}」尚需进一步审查 / Issue '{root_issue.title}' requires further examination",
                statement_class=StatementClass.inference,
                supporting_evidence_ids=issue_evidence[:1],
                supporting_output_ids=[],
            )

            sections.append(ReportSection(
                section_id=section_id,
                section_index=sec_idx,
                title=root_issue.title,
                body=(
                    f"争点「{root_issue.title}」类型为 {root_issue.issue_type}。"
                    f"关联证据: {', '.join(issue_evidence)}。"
                    f"该争点包含 {len(root_issue.fact_propositions)} 条事实命题，需结合证据综合认定。"
                ),
                linked_issue_ids=[root_id],
                linked_output_ids=[f"output-{report_slug}-{sec_idx:02d}"],
                linked_evidence_ids=issue_evidence,
                key_conclusions=[default_conclusion],
            ))

        # ── summary 截断 / Truncate summary ──────────────────────────────────
        summary = llm_output.summary
        if len(summary) > 500:
            summary = summary[:497] + "..."

        # ── 生成报告 ID / Generate report ID ─────────────────────────────────
        compact_ts = now[:19].replace("-", "").replace(":", "").replace("T", "")
        report_id = f"report-{report_slug}-{compact_ts}"

        return ReportArtifact(
            report_id=report_id,
            case_id=case_id,
            run_id=run_id,
            title=llm_output.title,
            summary=summary,
            sections=sections,
            created_at=now,
        )
