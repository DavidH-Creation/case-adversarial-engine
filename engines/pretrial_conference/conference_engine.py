"""
庭前会议编排器 — v1.5 顶层组件。
Pretrial conference engine — v1.5 top-level orchestrator.

五阶段流程 / Five-stage pipeline:
1. 证据提交   — EvidenceStateMachine.bulk_submit()
2. 质证       — CrossExaminationEngine.run()
3. 法官发问   — JudgeAgent.generate_questions()
4. 产物组装   — PretrialConferenceResult

合约保证 / Contract guarantees:
- 每个阶段独立容错，任一阶段 LLM 失败不影响后续阶段
- 证据生命周期通过 EvidenceStateMachine 强制合法
- JudgeAgent 只接收 admitted_for_discussion 证据
- 最终输出始终返回 PretrialConferenceResult，不抛异常
"""

from __future__ import annotations

from uuid import uuid4

from engines.shared.evidence_state_machine import EvidenceStateMachine
from engines.shared.models import (
    BlockingCondition,
    EvidenceGapItem,
    EvidenceIndex,
    EvidenceStatus,
    IssueTree,
    LLMClient,
)

from .agents.judge_agent import JudgeAgent
from .cross_examination_engine import CrossExaminationEngine
from .schemas import (
    CrossExaminationResult,
    JudgeQuestionSet,
    PretrialConferenceResult,
)


class PretrialConferenceEngine:
    """庭前会议编排器。

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
        self._sm = EvidenceStateMachine()
        self._cross_exam = CrossExaminationEngine(
            llm_client,
            model=model,
            temperature=temperature,
            max_retries=max_retries,
        )
        self._judge = JudgeAgent(
            llm_client,
            model=model,
            temperature=temperature,
            max_retries=max_retries,
        )

    async def run(
        self,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        plaintiff_party_id: str,
        defendant_party_id: str,
        plaintiff_evidence_ids: list[str] | None = None,
        defendant_evidence_ids: list[str] | None = None,
        *,
        evidence_gaps: list[EvidenceGapItem] | None = None,
        blocking_conditions: list[BlockingCondition] | None = None,
    ) -> PretrialConferenceResult:
        """执行庭前会议全流程。

        Args:
            issue_tree:              争点树
            evidence_index:          完整证据索引（含 private 证据）
            plaintiff_party_id:      原告 party_id
            defendant_party_id:      被告 party_id
            plaintiff_evidence_ids:  原告要提交的证据 ID 列表
            defendant_evidence_ids:  被告要提交的证据 ID 列表
            evidence_gaps:           可选，传递给 JudgeAgent
            blocking_conditions:     可选，传递给 JudgeAgent

        Returns:
            PretrialConferenceResult
        """
        run_id = f"run-conf-{uuid4().hex[:12]}"
        case_id = evidence_index.case_id

        # ------------------------------------------------------------------
        # Stage 1: 证据提交 (private → submitted)
        # ------------------------------------------------------------------
        current_index = evidence_index
        if plaintiff_evidence_ids:
            current_index = self._sm.bulk_submit(
                current_index,
                plaintiff_party_id,
                plaintiff_evidence_ids,
            )
        if defendant_evidence_ids:
            current_index = self._sm.bulk_submit(
                current_index,
                defendant_party_id,
                defendant_evidence_ids,
            )

        # ------------------------------------------------------------------
        # Stage 2: 质证 (submitted → challenged / admitted_for_discussion)
        # ------------------------------------------------------------------
        cross_result, current_index = await self._cross_exam.run(
            evidence_index=current_index,
            issue_tree=issue_tree,
            plaintiff_party_id=plaintiff_party_id,
            defendant_party_id=defendant_party_id,
        )

        # ------------------------------------------------------------------
        # Stage 3: 法官发问 (基于 admitted 证据)
        # ------------------------------------------------------------------
        admitted_evidence = [
            ev
            for ev in current_index.evidence
            if ev.status == EvidenceStatus.admitted_for_discussion
        ]

        if not admitted_evidence:
            judge_qs = JudgeQuestionSet(
                case_id=case_id,
                run_id=run_id,
                questions=[],
            )
        else:
            judge_qs = await self._judge.generate_questions(
                issue_tree=issue_tree,
                admitted_evidence=admitted_evidence,
                evidence_gaps=evidence_gaps,
                blocking_conditions=blocking_conditions,
                case_id=case_id,
                run_id=run_id,
                plaintiff_party_id=plaintiff_party_id,
                defendant_party_id=defendant_party_id,
            )

        # ------------------------------------------------------------------
        # Stage 4: 组装结果
        # ------------------------------------------------------------------
        return PretrialConferenceResult(
            case_id=case_id,
            run_id=run_id,
            cross_examination_result=cross_result,
            judge_questions=judge_qs,
            final_evidence_index=current_index,
        )
