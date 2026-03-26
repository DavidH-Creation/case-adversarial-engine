"""
RoundEngine — 三轮对抗辩论编排器。
RoundEngine — three-round adversarial debate orchestrator.

轮次结构（固定3轮）：
  Round 1 (claim):    原告提交主张+证据，被告提交抗辩+证据
  Round 2 (evidence): EvidenceManager 整理双方证据清单，标记冲突
  Round 3 (rebuttal): 原告针对被告抗辩反驳，被告针对原告主张反驳

Round structure (fixed 3 rounds):
  Round 1 (claim):    Plaintiff submits claims, defendant submits defenses
  Round 2 (evidence): EvidenceManager organizes evidence and flags conflicts
  Round 3 (rebuttal): Plaintiff rebuts defendant, defendant rebuts plaintiff
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from engines.shared.access_control import AccessController
from engines.shared.job_manager import JobManager
from engines.shared.models import (
    AccessDomain,
    AgentOutput,
    AgentRole,
    ArtifactRef,
    EvidenceIndex,
    IssueTree,
    JobError,
    LLMClient,
)
from engines.shared.workspace_manager import WorkspaceManager

from .agents.defendant import DefendantAgent
from .agents.evidence_mgr import EvidenceManagerAgent
from .agents.plaintiff import PlaintiffAgent
from .schemas import (
    AdversarialResult,
    Argument,
    ConflictEntry,
    MissingEvidenceReport,
    RoundConfig,
    RoundPhase,
    RoundState,
)
from .summarizer import AdversarialSummarizer


class RoundEngine:
    """三轮对抗辩论编排器。Three-round adversarial debate orchestrator.

    Args:
        llm_client:  符合 LLMClient 协议的客户端实例
        config:      轮次配置（可选，默认 RoundConfig()）
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: RoundConfig | None = None,
        workspace_manager: WorkspaceManager | None = None,
        job_manager: JobManager | None = None,
    ) -> None:
        self._llm = llm_client
        self._config = config or RoundConfig()
        self._access_ctrl = AccessController()
        self._workspace = workspace_manager
        self._job_manager = job_manager

    async def run(
        self,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        plaintiff_party_id: str,
        defendant_party_id: str,
    ) -> AdversarialResult:
        """执行完整的三轮对抗模拟。
        Execute the complete three-round adversarial simulation.

        Args:
            issue_tree:          已提取的争点树
            evidence_index:      证据索引（含完整证据列表）
            plaintiff_party_id:  原告方 party_id
            defendant_party_id:  被告方 party_id

        Returns:
            AdversarialResult 包含所有轮次输出和分析结果
        """
        run_id = f"run-adv-{uuid.uuid4().hex[:12]}"
        case_id = issue_tree.case_id
        all_evidence = evidence_index.evidence

        # ── Job 生命周期启动（可选）/ Job lifecycle start (optional) ──────
        job_id = ""
        if self._job_manager:
            job = self._job_manager.create_job(case_id, run_id, "adversarial_round")
            job_id = job.job_id
            self._job_manager.start_job(job_id)

        try:
            # 初始化代理
            plaintiff = PlaintiffAgent(self._llm, plaintiff_party_id, self._config)
            defendant = DefendantAgent(self._llm, defendant_party_id, self._config)
            ev_manager = EvidenceManagerAgent(self._llm, self._config)

            # 按角色过滤可见证据
            plaintiff_evidence = self._access_ctrl.filter_evidence_for_agent(
                role_code=AgentRole.plaintiff_agent.value,
                owner_party_id=plaintiff_party_id,
                all_evidence=all_evidence,
            )
            defendant_evidence = self._access_ctrl.filter_evidence_for_agent(
                role_code=AgentRole.defendant_agent.value,
                owner_party_id=defendant_party_id,
                all_evidence=all_evidence,
            )

            rounds: list[RoundState] = []
            all_outputs: list[AgentOutput] = []
            evidence_conflicts: list[ConflictEntry] = []

            # ── Round 1: 首轮主张 / claim ──────────────────────────────────
            state_id_r1 = f"state-r1-{uuid.uuid4().hex[:8]}"

            p_claim = await plaintiff.generate_claim(
                issue_tree=issue_tree,
                visible_evidence=plaintiff_evidence,
                context_outputs=[],
                run_id=run_id,
                state_id=state_id_r1,
                round_index=1,
            )
            p_claim = p_claim.model_copy(update={"case_id": case_id})
            if self._workspace:
                self._workspace.save_agent_output(p_claim, AccessDomain.owner_private)

            d_claim = await defendant.generate_claim(
                issue_tree=issue_tree,
                visible_evidence=defendant_evidence,
                context_outputs=[p_claim],
                run_id=run_id,
                state_id=state_id_r1,
                round_index=1,
            )
            d_claim = d_claim.model_copy(update={"case_id": case_id})
            if self._workspace:
                self._workspace.save_agent_output(d_claim, AccessDomain.owner_private)

            round1 = RoundState(
                round_number=1,
                phase=RoundPhase.claim,
                outputs=[p_claim, d_claim],
            )
            rounds.append(round1)
            all_outputs.extend([p_claim, d_claim])
            if self._job_manager:
                self._job_manager.update_progress(job_id, 0.33, "完成 Round 1 claim")

            # ── Round 2: 证据整理 / evidence ────────────────────────────────
            state_id_r2 = f"state-r2-{uuid.uuid4().hex[:8]}"

            ev_output, conflicts = await ev_manager.analyze(
                issue_tree=issue_tree,
                evidence_index=evidence_index,
                plaintiff_outputs=[p_claim],
                defendant_outputs=[d_claim],
                run_id=run_id,
                state_id=state_id_r2,
                round_index=2,
            )
            ev_output = ev_output.model_copy(update={"case_id": case_id})
            if self._workspace:
                self._workspace.save_agent_output(ev_output, AccessDomain.shared_common)
            evidence_conflicts.extend(conflicts)

            round2 = RoundState(
                round_number=2,
                phase=RoundPhase.evidence,
                outputs=[ev_output],
            )
            rounds.append(round2)
            all_outputs.append(ev_output)
            if self._job_manager:
                self._job_manager.update_progress(job_id, 0.66, "完成 Round 2 evidence")

            # ── Round 3: 针对性反驳 / rebuttal ──────────────────────────────
            state_id_r3 = f"state-r3-{uuid.uuid4().hex[:8]}"

            p_rebuttal = await plaintiff.generate_rebuttal(
                issue_tree=issue_tree,
                visible_evidence=plaintiff_evidence,
                context_outputs=all_outputs,
                opponent_outputs=[d_claim],
                run_id=run_id,
                state_id=state_id_r3,
                round_index=3,
            )
            p_rebuttal = p_rebuttal.model_copy(update={"case_id": case_id})
            if self._workspace:
                self._workspace.save_agent_output(p_rebuttal, AccessDomain.owner_private)

            d_rebuttal = await defendant.generate_rebuttal(
                issue_tree=issue_tree,
                visible_evidence=defendant_evidence,
                context_outputs=all_outputs,
                opponent_outputs=[p_claim],
                run_id=run_id,
                state_id=state_id_r3,
                round_index=3,
            )
            d_rebuttal = d_rebuttal.model_copy(update={"case_id": case_id})
            if self._workspace:
                self._workspace.save_agent_output(d_rebuttal, AccessDomain.owner_private)

            round3 = RoundState(
                round_number=3,
                phase=RoundPhase.rebuttal,
                outputs=[p_rebuttal, d_rebuttal],
            )
            rounds.append(round3)
            all_outputs.extend([p_rebuttal, d_rebuttal])

            # ── 后处理：提取最佳论点和未决争点 ─────────────────────────────
            plaintiff_best = self._extract_best_arguments(p_claim, p_rebuttal)
            defendant_best = self._extract_best_arguments(d_claim, d_rebuttal)
            unresolved_issues = self._compute_unresolved_issues(issue_tree, evidence_conflicts)
            missing_ev_report = self._build_missing_evidence_report(
                issue_tree, plaintiff_evidence, defendant_evidence,
                plaintiff_party_id, defendant_party_id,
            )

            result = AdversarialResult(
                case_id=case_id,
                run_id=run_id,
                job_id=job_id,
                rounds=rounds,
                plaintiff_best_arguments=plaintiff_best,
                defendant_best_defenses=defendant_best,
                unresolved_issues=unresolved_issues,
                evidence_conflicts=evidence_conflicts,
                missing_evidence_report=missing_ev_report,
            )

            # ── LLM 语义分析总结 / LLM semantic summary ─────────────────────
            summarizer = AdversarialSummarizer(self._llm, self._config)
            summary = await summarizer.summarize(result, issue_tree)
            final_result = result.model_copy(update={"summary": summary})

            # ── Job 完成 / Job completion ────────────────────────────────────
            if self._job_manager:
                result_ref = ArtifactRef(
                    object_type="AdversarialResult",
                    object_id=run_id,
                    storage_ref=f"run/{run_id}",
                )
                self._job_manager.complete_job(job_id, result_ref)

            return final_result

        except Exception as exc:
            if self._job_manager and job_id:
                self._job_manager.fail_job(
                    job_id,
                    JobError(code="round_engine_error", message=str(exc)),
                )
            raise

    # ------------------------------------------------------------------
    # 后处理辅助 / Post-processing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_best_arguments(
        *outputs: AgentOutput,
    ) -> list[Argument]:
        """从 AgentOutput 中提取为 Argument 列表（取引用证据最多的输出）。
        Extract best arguments from AgentOutputs.
        """
        best: list[Argument] = []
        for output in outputs:
            if not output.issue_ids or not output.evidence_citations:
                continue
            # 每个 issue 生成一条 Argument
            for issue_id in output.issue_ids:
                best.append(Argument(
                    issue_id=issue_id,
                    position=output.body[:500] if output.body else output.title,
                    supporting_evidence_ids=output.evidence_citations[:5],
                ))
        return best

    @staticmethod
    def _compute_unresolved_issues(
        issue_tree: IssueTree,
        conflicts: list[ConflictEntry],
    ) -> list[str]:
        """计算仍未解决的争点（有冲突的争点视为未解决）。
        Compute unresolved issues (issues with conflicts are unresolved).
        """
        conflicted_issue_ids = {c.issue_id for c in conflicts}
        # 所有 open 状态争点中存在冲突的视为未解决
        unresolved = []
        for issue in issue_tree.issues:
            if issue.issue_id in conflicted_issue_ids:
                unresolved.append(issue.issue_id)
            elif issue.status.value == "open":
                unresolved.append(issue.issue_id)
        return list(dict.fromkeys(unresolved))  # 去重保序

    @staticmethod
    def _build_missing_evidence_report(
        issue_tree: IssueTree,
        plaintiff_evidence: list,
        defendant_evidence: list,
        plaintiff_party_id: str,
        defendant_party_id: str,
    ) -> list[MissingEvidenceReport]:
        """分析各争点上哪方缺乏证据支撑。
        Analyze which party lacks evidence for each issue.
        """
        p_ev_ids = {e.evidence_id for e in plaintiff_evidence}
        d_ev_ids = {e.evidence_id for e in defendant_evidence}

        report = []
        for issue in issue_tree.issues:
            issue_ev_ids = set(issue.evidence_ids)
            # 判断原告侧该争点是否有证据
            p_has = bool(issue_ev_ids & p_ev_ids)
            d_has = bool(issue_ev_ids & d_ev_ids)

            if not p_has:
                report.append(MissingEvidenceReport(
                    issue_id=issue.issue_id,
                    missing_for_party_id=plaintiff_party_id,
                    description=f"争点「{issue.title}」原告方缺乏直接证据支撑",
                ))
            if not d_has:
                report.append(MissingEvidenceReport(
                    issue_id=issue.issue_id,
                    missing_for_party_id=defendant_party_id,
                    description=f"争点「{issue.title}」被告方缺乏直接证据支撑",
                ))
        return report
