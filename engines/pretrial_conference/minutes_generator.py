"""
庭前会议纪要生成器 — 规则层组件（零 LLM）。
Pretrial conference minutes generator — rule-based, no LLM.

将 PretrialConferenceResult 组装为 ReportArtifact，
包含以下章节 / sections:
1. 案件概况
2. 证据提交
3. 质证情况
4. 争点整理
5. 法官追问
6. 质证焦点清单
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from engines.shared.models import (
    EvidenceStatus,
    IssueTree,
    KeyConclusion,
    ReportArtifact,
    ReportSection,
)

from .schemas import PretrialConferenceResult


class MinutesGenerator:
    """庭前会议纪要生成器。"""

    def generate(
        self,
        result: PretrialConferenceResult,
        issue_tree: IssueTree,
    ) -> ReportArtifact:
        """生成庭前会议纪要。

        Args:
            result:     庭前会议结果
            issue_tree: 争点树

        Returns:
            ReportArtifact
        """
        sections: list[ReportSection] = []
        section_idx = 0

        # 回链 output_ids：质证结果 run_id + 法官追问 run_id
        xexam_output_id = result.cross_examination_result.run_id
        judge_output_id = result.judge_questions.run_id
        all_output_ids = sorted({oid for oid in (xexam_output_id, judge_output_id) if oid}) or [
            result.run_id
        ]

        # ------------------------------------------------------------------
        # 1. 案件概况
        # ------------------------------------------------------------------
        section_idx += 1
        issue_ids = [iss.issue_id for iss in issue_tree.issues]
        sections.append(
            ReportSection(
                section_id=f"sec-{section_idx:02d}",
                section_index=section_idx,
                title="案件概况",
                body=(
                    f"案件编号：{result.case_id}\n"
                    f"运行编号：{result.run_id}\n"
                    f"争点数量：{len(issue_tree.issues)}\n"
                    f"证据数量：{len(result.final_evidence_index.evidence)}"
                ),
                linked_issue_ids=issue_ids,
                linked_output_ids=all_output_ids,
                linked_evidence_ids=[],
            )
        )

        # ------------------------------------------------------------------
        # 2. 证据提交
        # ------------------------------------------------------------------
        section_idx += 1
        final_idx = result.final_evidence_index
        submitted_ev_ids = [
            ev.evidence_id for ev in final_idx.evidence if ev.status != EvidenceStatus.private
        ]
        body_lines = [f"共 {len(submitted_ev_ids)} 条证据进入质证程序。"]
        for ev in final_idx.evidence:
            if ev.status != EvidenceStatus.private:
                body_lines.append(
                    f"- {ev.evidence_id}: {ev.title} "
                    f"(owner: {ev.owner_party_id}, status: {ev.status.value})"
                )
        sections.append(
            ReportSection(
                section_id=f"sec-{section_idx:02d}",
                section_index=section_idx,
                title="证据提交",
                body="\n".join(body_lines) or "无证据提交。",
                linked_issue_ids=[],
                linked_output_ids=all_output_ids,
                linked_evidence_ids=submitted_ev_ids,
            )
        )

        # ------------------------------------------------------------------
        # 3. 质证情况
        # ------------------------------------------------------------------
        section_idx += 1
        xexam = result.cross_examination_result
        xexam_lines = [f"共 {len(xexam.records)} 条证据经质证。"]
        xexam_ev_ids: list[str] = []
        xexam_issue_ids: set[str] = set()
        for rec in xexam.records:
            xexam_ev_ids.append(rec.evidence_id)
            xexam_lines.append(f"\n### {rec.evidence_id}: {rec.evidence_title}")
            xexam_lines.append(f"- 所有方: {rec.owner_party_id}")
            xexam_lines.append(f"- 质证结果: {rec.result_status}")
            for op in rec.opinions:
                xexam_lines.append(f"  - [{op.dimension.value}] {op.verdict.value}: {op.reasoning}")
                xexam_issue_ids.update(op.issue_ids)
        sections.append(
            ReportSection(
                section_id=f"sec-{section_idx:02d}",
                section_index=section_idx,
                title="质证情况",
                body="\n".join(xexam_lines) or "无质证记录。",
                linked_issue_ids=sorted(xexam_issue_ids),
                linked_output_ids=[xexam_output_id],
                linked_evidence_ids=xexam_ev_ids,
            )
        )

        # ------------------------------------------------------------------
        # 4. 争点整理
        # ------------------------------------------------------------------
        section_idx += 1
        issue_lines = []
        for iss in issue_tree.issues:
            cat_str = f" [{iss.issue_category.value}]" if iss.issue_category else ""
            issue_lines.append(
                f"- {iss.issue_id}: {iss.title}{cat_str} (status: {iss.status.value})"
            )
        sections.append(
            ReportSection(
                section_id=f"sec-{section_idx:02d}",
                section_index=section_idx,
                title="争点整理",
                body="\n".join(issue_lines) or "无争点。",
                linked_issue_ids=issue_ids,
                linked_output_ids=all_output_ids,
                linked_evidence_ids=[],
            )
        )

        # ------------------------------------------------------------------
        # 5. 法官追问
        # ------------------------------------------------------------------
        section_idx += 1
        jq = result.judge_questions
        jq_lines = [f"共 {len(jq.questions)} 个追问。"]
        jq_ev_ids: list[str] = []
        jq_issue_ids: list[str] = []
        for q in jq.questions:
            jq_lines.append(f"\n### [{q.question_type.value}] (priority {q.priority})")
            jq_lines.append(f"- 问题: {q.question_text}")
            jq_lines.append(f"- 对象: {q.target_party_id}")
            jq_lines.append(f"- 争点: {q.issue_id}")
            jq_lines.append(f"- 相关证据: {q.evidence_ids}")
            jq_ev_ids.extend(q.evidence_ids)
            jq_issue_ids.append(q.issue_id)
        sections.append(
            ReportSection(
                section_id=f"sec-{section_idx:02d}",
                section_index=section_idx,
                title="法官追问",
                body="\n".join(jq_lines) or "无法官追问。",
                linked_issue_ids=sorted(set(jq_issue_ids)),
                linked_output_ids=[judge_output_id],
                linked_evidence_ids=sorted(set(jq_ev_ids)),
            )
        )

        # ------------------------------------------------------------------
        # 6. 质证焦点清单
        # ------------------------------------------------------------------
        section_idx += 1
        focus = xexam.focus_list
        focus_lines = [f"共 {len(focus)} 项质证焦点。"]
        focus_ev_ids: list[str] = []
        focus_issue_ids: list[str] = []
        for f in focus:
            focus_lines.append(
                f"- {f.evidence_id} / {f.issue_id} [{f.dimension.value}]: {f.dispute_summary}"
            )
            focus_ev_ids.append(f.evidence_id)
            focus_issue_ids.append(f.issue_id)
        sections.append(
            ReportSection(
                section_id=f"sec-{section_idx:02d}",
                section_index=section_idx,
                title="质证焦点清单",
                body="\n".join(focus_lines) or "无质证焦点。",
                linked_issue_ids=sorted(set(focus_issue_ids)),
                linked_output_ids=[xexam_output_id],
                linked_evidence_ids=sorted(set(focus_ev_ids)),
            )
        )

        # ------------------------------------------------------------------
        # 组装 ReportArtifact
        # ------------------------------------------------------------------
        all_ev_ids: set[str] = set()
        for s in sections:
            all_ev_ids.update(s.linked_evidence_ids)

        return ReportArtifact(
            report_id=f"report-conf-{uuid4().hex[:8]}",
            case_id=result.case_id,
            run_id=result.run_id,
            title=f"模拟庭前会议纪要 — {result.case_id}",
            summary=(
                f"庭前会议完成。质证 {len(xexam.records)} 条证据，"
                f"焦点 {len(focus)} 项，"
                f"法官追问 {len(jq.questions)} 个。"
            ),
            sections=sections,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            linked_evidence_ids=sorted(all_ev_ids),
        )
