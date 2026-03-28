"""
质证编排器 — v1.5 核心组件。
Cross-examination engine — v1.5 core component.

职责 / Responsibilities:
1. 从 evidence_index 中选取 submitted 状态的证据
2. 按 owner 分组，由对方通过 LLM 生成质证意见
3. 规则层校验（过滤幻觉 ID、无效枚举）
4. 规则层决定状态迁移：任一维度 challenged → challenged；全部 accepted → admitted
5. 通过 EvidenceStateMachine 执行迁移
6. 输出 CrossExaminationResult + 更新后的 EvidenceIndex

合约保证 / Contract guarantees:
- 只有 submitted 状态的证据参与质证
- private / admitted_for_discussion 证据不会被传入 LLM
- 幻觉 evidence_id / issue_id 被过滤
- 无效 dimension / verdict 枚举值被过滤
- LLM 失败时返回空结果，不抛异常
- 证据状态迁移通过 EvidenceStateMachine 强制合法
"""

from __future__ import annotations

from uuid import uuid4

from engines.shared.evidence_state_machine import EvidenceStateMachine
from engines.shared.models import (
    EvidenceIndex,
    EvidenceStatus,
    IssueTree,
    LLMClient,
)

from .prompts.civil_loan import (
    CROSS_EXAM_SYSTEM,
    build_cross_exam_user_prompt,
)
from .schemas import (
    CrossExaminationDimension,
    CrossExaminationFocusItem,
    CrossExaminationOpinion,
    CrossExaminationRecord,
    CrossExaminationResult,
    CrossExaminationVerdict,
    LLMCrossExaminationOutput,
)


class CrossExaminationEngine:
    """质证编排器。

    Args:
        llm_client:  符合 LLMClient 协议的客户端实例
        model:       LLM 模型标识
        temperature: 生成温度
        max_retries: LLM 调用失败时的最大重试次数
    """

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str,
        temperature: float,
        max_retries: int,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._sm = EvidenceStateMachine()

    async def run(
        self,
        evidence_index: EvidenceIndex,
        issue_tree: IssueTree,
        plaintiff_party_id: str,
        defendant_party_id: str,
    ) -> tuple[CrossExaminationResult, EvidenceIndex]:
        """执行质证流程。

        Returns:
            (CrossExaminationResult, 更新后的 EvidenceIndex)
        """
        run_id = f"run-xexam-{uuid4().hex[:12]}"
        case_id = evidence_index.case_id

        # 构建已知 ID 集合
        known_evidence_ids: set[str] = {
            ev.evidence_id for ev in evidence_index.evidence
        }
        known_issue_ids: set[str] = {
            iss.issue_id for iss in issue_tree.issues
        }

        # 只取 submitted 证据
        submitted = [
            ev
            for ev in evidence_index.evidence
            if ev.status == EvidenceStatus.submitted
        ]

        if not submitted:
            return (
                CrossExaminationResult(case_id=case_id, run_id=run_id),
                evidence_index,
            )

        # 按 owner 分组
        plaintiff_ev = [
            ev for ev in submitted if ev.owner_party_id == plaintiff_party_id
        ]
        defendant_ev = [
            ev for ev in submitted if ev.owner_party_id == defendant_party_id
        ]

        all_opinions: list[CrossExaminationOpinion] = []

        # 被告质证原告证据
        if plaintiff_ev:
            ops = await self._examine_batch(
                evidences=plaintiff_ev,
                examiner_party_id=defendant_party_id,
                examiner_role="被告代理律师",
                issue_tree=issue_tree,
                known_evidence_ids=known_evidence_ids,
                known_issue_ids=known_issue_ids,
            )
            all_opinions.extend(ops)

        # 原告质证被告证据
        if defendant_ev:
            ops = await self._examine_batch(
                evidences=defendant_ev,
                examiner_party_id=plaintiff_party_id,
                examiner_role="原告代理律师",
                issue_tree=issue_tree,
                known_evidence_ids=known_evidence_ids,
                known_issue_ids=known_issue_ids,
            )
            all_opinions.extend(ops)

        # 构建 records + 状态迁移
        examiner_map = {
            plaintiff_party_id: defendant_party_id,
            defendant_party_id: plaintiff_party_id,
        }
        records, focus_list, updated_index = self._build_records_and_transition(
            all_opinions=all_opinions,
            submitted_evidence=submitted,
            evidence_index=evidence_index,
            examiner_map=examiner_map,
        )

        return (
            CrossExaminationResult(
                case_id=case_id,
                run_id=run_id,
                records=records,
                focus_list=focus_list,
            ),
            updated_index,
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    async def _examine_batch(
        self,
        evidences: list,
        examiner_party_id: str,
        examiner_role: str,
        issue_tree: IssueTree,
        known_evidence_ids: set[str],
        known_issue_ids: set[str],
    ) -> list[CrossExaminationOpinion]:
        """调用 LLM 对一批证据进行质证，返回校验后的意见列表。"""
        system = CROSS_EXAM_SYSTEM
        user = build_cross_exam_user_prompt(
            evidences=evidences,
            issue_tree=issue_tree,
            examiner_role=examiner_role,
        )

        for _attempt in range(self._max_retries + 1):
            try:
                raw = await self._llm.create_message(
                    system=system,
                    user=user,
                    model=self._model,
                    temperature=self._temperature,
                )
                return self._parse_and_validate(
                    raw,
                    examiner_party_id=examiner_party_id,
                    known_evidence_ids=known_evidence_ids,
                    known_issue_ids=known_issue_ids,
                )
            except Exception:  # noqa: BLE001
                pass

        return []

    def _parse_and_validate(
        self,
        raw: str,
        examiner_party_id: str,
        known_evidence_ids: set[str],
        known_issue_ids: set[str],
    ) -> list[CrossExaminationOpinion]:
        """解析 LLM 输出并校验，返回合法意见列表。"""
        from engines.shared.json_utils import _extract_json_object

        data = _extract_json_object(raw)
        llm_out = LLMCrossExaminationOutput.model_validate(data)

        result: list[CrossExaminationOpinion] = []
        for item in llm_out.opinions:
            # 过滤幻觉 evidence_id
            if item.evidence_id not in known_evidence_ids:
                continue

            # 校验 dimension 枚举
            try:
                dimension = CrossExaminationDimension(item.dimension)
            except ValueError:
                continue

            # 校验 verdict 枚举
            try:
                verdict = CrossExaminationVerdict(item.verdict)
            except ValueError:
                continue

            # 过滤幻觉 issue_ids
            clean_issue_ids = [
                iid for iid in item.issue_ids if iid in known_issue_ids
            ]
            if not clean_issue_ids:
                continue

            result.append(
                CrossExaminationOpinion(
                    evidence_id=item.evidence_id,
                    issue_ids=clean_issue_ids,
                    dimension=dimension,
                    verdict=verdict,
                    reasoning=item.reasoning or "无理由",
                    examiner_party_id=examiner_party_id,
                )
            )

        return result

    def _build_records_and_transition(
        self,
        all_opinions: list[CrossExaminationOpinion],
        submitted_evidence: list,
        evidence_index: EvidenceIndex,
        examiner_map: dict[str, str],
    ) -> tuple[list[CrossExaminationRecord], list[CrossExaminationFocusItem], EvidenceIndex]:
        """构建质证记录、焦点清单，并执行证据状态迁移。"""
        # 按 evidence_id 分组
        opinions_by_ev: dict[str, list[CrossExaminationOpinion]] = {}
        for op in all_opinions:
            opinions_by_ev.setdefault(op.evidence_id, []).append(op)

        records: list[CrossExaminationRecord] = []
        focus_list: list[CrossExaminationFocusItem] = []
        updated_evidence = list(evidence_index.evidence)

        for ev in submitted_evidence:
            ev_opinions = opinions_by_ev.get(ev.evidence_id, [])

            # 无意见（LLM 失败或未返回该证据的意见）→ 跳过，证据保持原状
            if not ev_opinions:
                continue

            # 规则：任一维度 challenged → challenged；全部 accepted → admitted
            has_challenged = any(
                op.verdict == CrossExaminationVerdict.challenged
                for op in ev_opinions
            )

            if has_challenged:
                result_status = "challenged"
                examiner_id = examiner_map.get(ev.owner_party_id, "system")
                try:
                    new_ev = self._sm.challenge(ev, examiner_id)
                    for i, e in enumerate(updated_evidence):
                        if e.evidence_id == ev.evidence_id:
                            updated_evidence[i] = new_ev
                            break
                except Exception:  # noqa: BLE001
                    pass
            else:
                result_status = "admitted_for_discussion"
                try:
                    new_ev = self._sm.admit(ev)
                    for i, e in enumerate(updated_evidence):
                        if e.evidence_id == ev.evidence_id:
                            updated_evidence[i] = new_ev
                            break
                except Exception:  # noqa: BLE001
                    pass

            records.append(
                CrossExaminationRecord(
                    evidence_id=ev.evidence_id,
                    evidence_title=ev.title,
                    owner_party_id=ev.owner_party_id,
                    opinions=ev_opinions,
                    result_status=result_status,
                )
            )

            # 焦点清单：challenged 意见 → focus item
            for op in ev_opinions:
                if op.verdict == CrossExaminationVerdict.challenged:
                    focus_list.append(
                        CrossExaminationFocusItem(
                            evidence_id=op.evidence_id,
                            issue_id=op.issue_ids[0],
                            dimension=op.dimension,
                            dispute_summary=op.reasoning,
                        )
                    )

        return (
            records,
            focus_list,
            evidence_index.model_copy(update={"evidence": updated_evidence}),
        )
