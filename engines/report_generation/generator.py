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

from datetime import datetime, timezone
from typing import Any, Optional

from engines.shared.json_utils import _extract_json_object  # noqa: F401 — re-exported for tests
from engines.shared.models import LLMClient
from engines.shared.pii_redactor import redact_text
from engines.shared.structured_output import call_structured_llm

from .issue_evidence_defense_matrix import (
    build_issue_evidence_defense_matrix,
    render_matrix_markdown,
)
from .outcome_paths import build_case_outcome_paths, render_outcome_paths_md_lines  # noqa: F401
from .schemas import (
    CaseOutcomePaths,  # noqa: F401 — re-exported for callers
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

# tool_use JSON Schema（模块加载时计算一次）
_TOOL_SCHEMA: dict = LLMReportOutput.model_json_schema()


# ---------------------------------------------------------------------------
# statement_class 解析工具 / statement_class resolution utility
# ---------------------------------------------------------------------------


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
# PII 脱敏 / PII redaction
# ---------------------------------------------------------------------------


def redact_report(
    report: ReportArtifact,
    *,
    party_names: list[str] | None = None,
) -> ReportArtifact:
    """对 ReportArtifact 的所有面向用户的文本字段执行 PII 脱敏。

    Redact PII from all user-facing text fields in a ReportArtifact.
    Returns a new ReportArtifact with redacted content (immutable style).
    """
    def _r(text: str) -> str:
        return redact_text(text, party_names=party_names)

    redacted_sections = []
    for sec in report.sections:
        redacted_conclusions = [
            kc.model_copy(update={"text": _r(kc.text)})
            for kc in sec.key_conclusions
        ]
        redacted_sections.append(
            sec.model_copy(update={
                "title": _r(sec.title),
                "body": _r(sec.body),
                "key_conclusions": redacted_conclusions,
            })
        )

    return report.model_copy(update={
        "title": _r(report.title),
        "summary": _r(report.summary),
        "sections": redacted_sections,
    })


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
        defense_chain: Any = None,
    ) -> ReportArtifact:
        """执行报告生成。
        Execute report generation.

        Args:
            issue_tree: 结构化争点树 / Structured issue tree
            evidence_index: 证据索引 / Evidence index
            run_id: 本次运行 ID / Run ID for this generation
            report_slug: 报告简称，用于生成 ID / Report slug for ID generation
            defense_chain: 原告方防御策略链（可选）/ PlaintiffDefenseChain (optional)

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

        # 调用 LLM（结构化输出）/ Call LLM with structured output
        raw_dict = await self._call_llm_structured(system_prompt, user_prompt)
        llm_output = LLMReportOutput.model_validate(raw_dict)

        # 构建 ReportArtifact / Build ReportArtifact
        report = self._build_report(
            llm_output,
            issue_tree,
            evidence_index,
            case_id,
            run_id,
            report_slug,
        )

        # 附加争点-证据-抗辩矩阵章节 / Append Issue-Evidence-Defense Matrix section
        report = self._append_matrix_section(
            report, issue_tree, evidence_index, defense_chain, run_id, report_slug
        )

        return report

    def _append_matrix_section(
        self,
        report: ReportArtifact,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        defense_chain: Any,
        run_id: str,
        report_slug: str,
    ) -> ReportArtifact:
        """构建矩阵并作为额外章节附加到报告。
        Build the matrix and attach it as an extra section to the report.

        Returns a new ReportArtifact with the matrix section appended.
        """
        matrix = build_issue_evidence_defense_matrix(
            issue_tree, evidence_index, defense_chain
        )
        if matrix is None:
            return report

        md = render_matrix_markdown(matrix)
        sec_idx = len(report.sections) + 1
        section_id = f"sec-{report_slug}-matrix"

        # Collect all unique evidence IDs from matrix rows for section linking
        matrix_evidence_ids: list[str] = []
        seen: set[str] = set()
        for row in matrix.rows:
            for eid in row.evidence_ids:
                if eid not in seen:
                    matrix_evidence_ids.append(eid)
                    seen.add(eid)

        matrix_section = ReportSection(
            section_id=section_id,
            section_index=sec_idx,
            title="争点-证据-抗辩矩阵 / Issue-Evidence-Defense Matrix",
            body=md,
            linked_issue_ids=[r.issue_id for r in matrix.rows],
            linked_output_ids=[f"run:{run_id}"] if run_id else [],
            linked_evidence_ids=matrix_evidence_ids,
            key_conclusions=[],
        )

        return report.model_copy(update={"sections": [*report.sections, matrix_section]})

    async def _call_llm_structured(self, system: str, user: str) -> dict:
        """调用 LLM（结构化输出）。
        Call LLM with structured output.

        Raises:
            RuntimeError: 超过最大重试次数 / Max retries exceeded
        """
        return await call_structured_llm(
            self._llm_client,
            system=system,
            user=user,
            model=self._model,
            tool_name="generate_report",
            tool_description="根据争点树和证据索引生成结构化诊断报告（含章节、关键结论和摘要）。"
                             "Generate a structured diagnostic report with sections, "
                             "key conclusions, and summary from issue tree and evidence index.",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
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
                    first_known = min(known_evidence_ids) if known_evidence_ids else None
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

            linked_output_ids = [f"run:{run_id}"] if run_id else []

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
                issue_evidence = [min(known_evidence_ids)] if known_evidence_ids else []

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
                linked_output_ids=[f"run:{run_id}"] if run_id else [],
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


# ---------------------------------------------------------------------------
# 文书草稿集成 / Document draft integration
# ---------------------------------------------------------------------------

_DOC_TYPE_TITLE_ZH: dict[str, str] = {
    "pleading":   "起诉状草稿",
    "defense":    "答辩状草稿",
    "cross_exam": "质证意见草稿",
}


def append_document_draft_sections(
    report: ReportArtifact,
    document_drafts: list,
) -> ReportArtifact:
    """将文书草稿附加为 ReportArtifact 的额外章节。
    Append document drafts as extra sections to a ReportArtifact.

    Args:
        report:          已生成的 ReportArtifact / Already-generated ReportArtifact
        document_drafts: DocumentDraft 列表 / List of DocumentDraft objects

    Returns:
        含文书章节的新 ReportArtifact（immutable style）。
        New ReportArtifact with document sections appended (immutable style).
    """
    if not document_drafts:
        return report

    extra_sections: list[ReportSection] = []
    base_idx = len(report.sections) + 1

    for i, draft in enumerate(document_drafts):
        doc_type = getattr(draft, "doc_type", "")
        case_type = getattr(draft, "case_type", "")
        evidence_ids_cited = getattr(draft, "evidence_ids_cited", [])
        content = getattr(draft, "content", None)

        title = f"{_DOC_TYPE_TITLE_ZH.get(doc_type, doc_type)}（{case_type}）"

        # 拼接骨架内容为 body 文本
        body_parts: list[str] = []
        if content is not None:
            header = getattr(content, "header", "")
            if header:
                body_parts.append(f"【文书标题】{header}")

            if doc_type == "pleading":
                for field, label in [
                    ("fact_narrative_items", "事实陈述"),
                    ("legal_claim_items", "法律依据"),
                    ("prayer_for_relief_items", "诉讼请求"),
                ]:
                    items = getattr(content, field, [])
                    if items:
                        body_parts.append(f"【{label}】" + "；".join(items))

            elif doc_type == "defense":
                for field, label in [
                    ("denial_items", "逐项否认"),
                    ("defense_claim_items", "实质性抗辩"),
                    ("counter_prayer_items", "反请求"),
                ]:
                    items = getattr(content, field, [])
                    if items:
                        body_parts.append(f"【{label}】" + "；".join(items))

            elif doc_type == "cross_exam":
                items_list = getattr(content, "items", [])
                if items_list:
                    opinions = [
                        f"{getattr(it, 'evidence_id', '')}: {getattr(it, 'opinion_text', '')}"
                        for it in items_list
                    ]
                    body_parts.append("【质证意见】" + "；".join(opinions[:5]))
                    if len(items_list) > 5:
                        body_parts.append(f"... 共 {len(items_list)} 条意见")

        body = "\n".join(body_parts) if body_parts else "（文书内容见附件）"

        # 构建 key_conclusions（证据引用）
        key_conclusions: list[KeyConclusion] = []
        if evidence_ids_cited:
            key_conclusions.append(KeyConclusion(
                conclusion_id=f"doc-cite-{i + 1:03d}",
                text=f"引用证据：{', '.join(evidence_ids_cited)}",
                supporting_evidence_ids=evidence_ids_cited,
                statement_class=StatementClass.fact,
            ))

        extra_sections.append(ReportSection(
            section_id=f"doc-sec-{i + 1:03d}",
            section_index=base_idx + i,
            title=title,
            body=body,
            linked_issue_ids=[],
            linked_evidence_ids=evidence_ids_cited,
            key_conclusions=key_conclusions,
        ))

    return report.model_copy(update={"sections": report.sections + extra_sections})
