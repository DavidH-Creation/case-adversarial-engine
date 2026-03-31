"""
程序法官代理 — v1.5 核心组件。
Judge agent — v1.5 core component.

职责 / Responsibilities:
1. 基于已采纳证据和未解决争点，通过 LLM 生成追问
2. 消费 v1.2 产物增强追问质量（EvidenceGapItem, BlockingCondition）
3. 规则层校验（过滤幻觉 ID、无效枚举、priority 截断）
4. 硬上限 10 个问题

合约保证 / Contract guarantees:
- 构造器断言：所有传入证据必须 status == admitted_for_discussion
- 只引用已知 evidence_id 和 issue_id
- 只针对 unresolved (open) issues 生成追问
- 无效 question_type 被丢弃
- priority 截断到 [1, 10]
- LLM 失败时返回空 JudgeQuestionSet，不抛异常
"""

from __future__ import annotations

from engines.shared.models import (
    BlockingCondition,
    Evidence,
    EvidenceGapItem,
    EvidenceStatus,
    IssueStatus,
    IssueTree,
    LLMClient,
)

from ..prompts.judge import JUDGE_SYSTEM, build_judge_user_prompt
from ..schemas import (
    JudgeQuestion,
    JudgeQuestionSet,
    JudgeQuestionType,
    LLMJudgeQuestionOutput,
)

_MAX_QUESTIONS = 10


class JudgeAgent:
    """程序法官代理。

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

    async def generate_questions(
        self,
        issue_tree: IssueTree,
        admitted_evidence: list[Evidence],
        *,
        evidence_gaps: list[EvidenceGapItem] | None = None,
        blocking_conditions: list[BlockingCondition] | None = None,
        case_id: str,
        run_id: str,
        plaintiff_party_id: str = "",
        defendant_party_id: str = "",
    ) -> JudgeQuestionSet:
        """生成法官追问。

        Args:
            issue_tree:          争点树
            admitted_evidence:   已采纳证据列表（必须全部 admitted_for_discussion）
            evidence_gaps:       可选，证据缺口列表（增强追问质量）
            blocking_conditions: 可选，阻断条件列表（增强追问质量）
            case_id:             案件 ID
            run_id:              运行 ID
            plaintiff_party_id:  原告 party_id
            defendant_party_id:  被告 party_id

        Returns:
            JudgeQuestionSet

        Raises:
            ValueError: 传入了非 admitted_for_discussion 的证据
        """
        # 三层防泄露之二：构造器断言
        for ev in admitted_evidence:
            if ev.status != EvidenceStatus.admitted_for_discussion:
                raise ValueError(
                    f"JudgeAgent 只接受 admitted_for_discussion 证据，"
                    f"收到 {ev.evidence_id} status={ev.status.value}。"
                )

        # 构建已知 ID 集合
        known_evidence_ids = {ev.evidence_id for ev in admitted_evidence}
        known_issue_ids = {iss.issue_id for iss in issue_tree.issues}

        # 只取 open 争点
        open_issues = [iss for iss in issue_tree.issues if iss.status == IssueStatus.open]

        if not open_issues:
            return JudgeQuestionSet(case_id=case_id, run_id=run_id, questions=[])

        # 调用 LLM
        questions = await self._call_llm(
            open_issues=open_issues,
            admitted_evidence=admitted_evidence,
            evidence_gaps=evidence_gaps,
            blocking_conditions=blocking_conditions,
            known_evidence_ids=known_evidence_ids,
            known_issue_ids=known_issue_ids,
            plaintiff_party_id=plaintiff_party_id,
            defendant_party_id=defendant_party_id,
        )

        return JudgeQuestionSet(
            case_id=case_id,
            run_id=run_id,
            questions=questions[:_MAX_QUESTIONS],
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        open_issues: list,
        admitted_evidence: list[Evidence],
        evidence_gaps: list[EvidenceGapItem] | None,
        blocking_conditions: list[BlockingCondition] | None,
        known_evidence_ids: set[str],
        known_issue_ids: set[str],
        plaintiff_party_id: str,
        defendant_party_id: str,
    ) -> list[JudgeQuestion]:
        """调用 LLM 并返回校验后的问题列表。"""
        system = JUDGE_SYSTEM
        user = build_judge_user_prompt(
            issues=open_issues,
            admitted_evidence=admitted_evidence,
            evidence_gaps=evidence_gaps,
            blocking_conditions=blocking_conditions,
            plaintiff_party_id=plaintiff_party_id,
            defendant_party_id=defendant_party_id,
        )

        from engines.shared.llm_utils import call_llm_with_retry

        try:
            raw = await call_llm_with_retry(
                self._llm,
                system=system,
                user=user,
                model=self._model,
                temperature=self._temperature,
                max_retries=self._max_retries,
            )
            return self._parse_and_validate(
                raw,
                known_evidence_ids=known_evidence_ids,
                known_issue_ids=known_issue_ids,
            )
        except Exception:  # noqa: BLE001
            return []

    def _parse_and_validate(
        self,
        raw: str,
        known_evidence_ids: set[str],
        known_issue_ids: set[str],
    ) -> list[JudgeQuestion]:
        """解析并校验 LLM 输出。"""
        from engines.shared.json_utils import _extract_json_object

        data = _extract_json_object(raw)
        llm_out = LLMJudgeQuestionOutput.model_validate(data)

        result: list[JudgeQuestion] = []
        for item in llm_out.questions:
            # 校验 issue_id
            if item.issue_id not in known_issue_ids:
                continue

            # 校验 question_type
            try:
                qtype = JudgeQuestionType(item.question_type)
            except ValueError:
                continue

            # 过滤幻觉 evidence_ids
            clean_ev_ids = [eid for eid in item.evidence_ids if eid in known_evidence_ids]
            if not clean_ev_ids:
                continue

            # priority 截断到 [1, 10]
            priority = max(1, min(10, item.priority))

            if not item.question_text or not item.question_id:
                continue

            result.append(
                JudgeQuestion(
                    question_id=item.question_id,
                    issue_id=item.issue_id,
                    evidence_ids=clean_ev_ids,
                    question_text=item.question_text,
                    target_party_id=item.target_party_id or "unknown",
                    question_type=qtype,
                    priority=priority,
                )
            )

        return result
