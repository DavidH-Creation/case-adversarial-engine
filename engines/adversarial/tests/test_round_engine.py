"""
RoundEngine 集成测试 — 使用 mock LLMClient 验证三轮编排逻辑。
RoundEngine integration tests — verify three-round orchestration with mock LLMClient.
"""

from __future__ import annotations

import json
import pytest

from engines.shared.models import (
    AccessDomain,
    Evidence,
    EvidenceIndex,
    EvidenceType,
    Issue,
    IssueTree,
    IssueType,
)
from engines.adversarial.round_engine import RoundEngine
from engines.adversarial.schemas import (
    AdversarialResult,
    AdversarialSummary,
    RoundConfig,
    RoundPhase,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-loan-001"
PLAINTIFF_ID = "party-p-001"
DEFENDANT_ID = "party-d-001"


def _make_response(title: str, party_id: str, issue_id: str = "issue-001") -> str:
    return json.dumps(
        {
            "title": title,
            "body": f"详细论述，引用证据 ev-001。当事方: {party_id}",
            "case_id": CASE_ID,
            "issue_ids": [issue_id],
            "evidence_citations": ["ev-001"],
            "risk_flags": [],
            "arguments": [
                {
                    "issue_id": issue_id,
                    "position": title,
                    "supporting_evidence_ids": ["ev-001"],
                    "legal_basis": "《民法典》第667条",
                }
            ],
            "conflicts": [],
        },
        ensure_ascii=False,
    )


# 第 6 条响应：AdversarialSummarizer 返回的有效 JSON
_SUMMARY_RESPONSE = json.dumps(
    {
        "plaintiff_strongest_arguments": [
            {
                "issue_id": "issue-001",
                "position": "原告有转账记录，证明借款已实际交付",
                "evidence_ids": ["ev-001"],
                "reasoning": "直接证明借贷要件，被告无有效反证",
            }
        ],
        "defendant_strongest_defenses": [
            {
                "issue_id": "issue-001",
                "position": "被告否认收款，质疑转账用途",
                "evidence_ids": ["ev-001"],
                "reasoning": "动摇借贷关系成立基础",
            }
        ],
        "unresolved_issues": [
            {
                "issue_id": "issue-001",
                "issue_title": "借贷关系是否成立",
                "why_unresolved": "双方证据存在正面冲突，未有定论",
            }
        ],
        "missing_evidence_report": [
            {
                "issue_id": "issue-001",
                "missing_for_party_id": DEFENDANT_ID,
                "gap_description": "被告缺乏收款否认的书面证据",
            }
        ],
        "overall_assessment": "原告证据链较完整，被告抗辩薄弱，但争点尚未闭合。",
    },
    ensure_ascii=False,
)


class SequentialMockLLM:
    """按顺序返回不同响应的 mock LLM（模拟真实对话轮次）。

    6 次调用：
      1. 原告首轮主张
      2. 被告首轮抗辩
      3. EvidenceManager 证据整理
      4. 原告反驳
      5. 被告反驳
      6. AdversarialSummarizer 语义总结
    """

    def __init__(self):
        self.calls: list[str] = []
        self._responses = [
            _make_response("原告首轮主张：借款关系成立", PLAINTIFF_ID),
            _make_response("被告首轮抗辩：借款未成立", DEFENDANT_ID),
            # Round 2: EvidenceManager
            json.dumps(
                {
                    "title": "证据整理",
                    "body": "双方证据存在冲突。",
                    "case_id": CASE_ID,
                    "issue_ids": ["issue-001"],
                    "evidence_citations": ["ev-001"],
                    "risk_flags": [],
                    "conflicts": [
                        {
                            "issue_id": "issue-001",
                            "plaintiff_evidence_ids": ["ev-001"],
                            "defendant_evidence_ids": [],
                            "conflict_description": "原告有转账记录但被告否认收款",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            # Round 3
            _make_response("原告反驳：被告抗辩不成立", PLAINTIFF_ID),
            _make_response("被告反驳：原告主张无效", DEFENDANT_ID),
            # Round 4 (summarizer)
            _SUMMARY_RESPONSE,
        ]
        self._idx = 0

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        response = self._responses[self._idx % len(self._responses)]
        self.calls.append(user[:50])
        self._idx += 1
        return response


@pytest.fixture
def mock_llm() -> SequentialMockLLM:
    return SequentialMockLLM()


@pytest.fixture
def config() -> RoundConfig:
    return RoundConfig(max_tokens_per_output=1000, max_retries=2)


@pytest.fixture
def issue_tree() -> IssueTree:
    return IssueTree(
        case_id=CASE_ID,
        issues=[
            Issue(
                issue_id="issue-001",
                case_id=CASE_ID,
                title="借贷关系是否成立",
                issue_type=IssueType.factual,
                evidence_ids=["ev-001"],
            ),
        ],
    )


@pytest.fixture
def evidence_index() -> EvidenceIndex:
    return EvidenceIndex(
        case_id=CASE_ID,
        evidence=[
            Evidence(
                evidence_id="ev-001",
                case_id=CASE_ID,
                owner_party_id=PLAINTIFF_ID,
                title="银行转账记录",
                source="原告提交",
                summary="2023-01-01向被告账户转账5万元",
                evidence_type=EvidenceType.electronic_data,
                target_fact_ids=["fact-001"],
                access_domain=AccessDomain.shared_common,
            ),
            Evidence(
                evidence_id="ev-002",
                case_id=CASE_ID,
                owner_party_id=DEFENDANT_ID,
                title="被告私有证据",
                source="被告提交",
                summary="被告自述未收到款项",
                evidence_type=EvidenceType.witness_statement,
                target_fact_ids=["fact-002"],
                access_domain=AccessDomain.owner_private,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# RoundEngine 测试
# ---------------------------------------------------------------------------


class TestRoundEngine:
    @pytest.mark.asyncio
    async def test_run_returns_adversarial_result(
        self, mock_llm, config, issue_tree, evidence_index
    ):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        assert isinstance(result, AdversarialResult)
        assert result.case_id == CASE_ID
        assert result.run_id.startswith("run-adv-")

    @pytest.mark.asyncio
    async def test_three_rounds_produced(self, mock_llm, config, issue_tree, evidence_index):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        assert len(result.rounds) == 3
        assert result.rounds[0].phase == RoundPhase.claim
        assert result.rounds[1].phase == RoundPhase.evidence
        assert result.rounds[2].phase == RoundPhase.rebuttal

    @pytest.mark.asyncio
    async def test_round1_has_two_outputs(self, mock_llm, config, issue_tree, evidence_index):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        round1 = result.rounds[0]
        assert len(round1.outputs) == 2
        role_codes = {o.agent_role_code for o in round1.outputs}
        assert "plaintiff_agent" in role_codes
        assert "defendant_agent" in role_codes

    @pytest.mark.asyncio
    async def test_round2_has_evidence_manager_output(
        self, mock_llm, config, issue_tree, evidence_index
    ):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        round2 = result.rounds[1]
        assert len(round2.outputs) == 1
        assert round2.outputs[0].agent_role_code == "evidence_manager"

    @pytest.mark.asyncio
    async def test_round3_has_two_rebuttal_outputs(
        self, mock_llm, config, issue_tree, evidence_index
    ):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        round3 = result.rounds[2]
        assert len(round3.outputs) == 2
        for output in round3.outputs:
            assert output.round_index == 3

    @pytest.mark.asyncio
    async def test_evidence_isolation_respected(self, mock_llm, config, issue_tree, evidence_index):
        """被告私有证据 ev-002 不应出现在原告视角的 LLM 调用中。"""
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )
        # 原告的第一轮 prompt 不包含被告私有证据 ID
        first_plaintiff_call = mock_llm.calls[0]
        assert "ev-002" not in first_plaintiff_call

    @pytest.mark.asyncio
    async def test_all_outputs_have_correct_case_id(
        self, mock_llm, config, issue_tree, evidence_index
    ):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        for round_state in result.rounds:
            for output in round_state.outputs:
                assert output.case_id == CASE_ID

    @pytest.mark.asyncio
    async def test_best_arguments_extracted(self, mock_llm, config, issue_tree, evidence_index):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        assert len(result.plaintiff_best_arguments) >= 1
        assert len(result.defendant_best_defenses) >= 1
        for arg in result.plaintiff_best_arguments:
            assert len(arg.supporting_evidence_ids) >= 1

    @pytest.mark.asyncio
    async def test_evidence_conflicts_populated(self, mock_llm, config, issue_tree, evidence_index):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        # SequentialMockLLM 中的 EvidenceManager 响应包含1个冲突
        assert len(result.evidence_conflicts) == 1
        assert result.evidence_conflicts[0].issue_id == "issue-001"

    @pytest.mark.asyncio
    async def test_unresolved_issues_contains_conflicted(
        self, mock_llm, config, issue_tree, evidence_index
    ):
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        # issue-001 有冲突，应在 unresolved_issues 中
        assert "issue-001" in result.unresolved_issues

    @pytest.mark.asyncio
    async def test_llm_called_six_times(self, mock_llm, config, issue_tree, evidence_index):
        """6次 LLM 调用：R1原告 + R1被告 + R2证据管理 + R3原告 + R3被告 + Summarizer。"""
        engine = RoundEngine(mock_llm, config)
        await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        assert len(mock_llm.calls) == 6

    @pytest.mark.asyncio
    async def test_result_includes_summary(self, mock_llm, config, issue_tree, evidence_index):
        """RoundEngine.run() 后 result.summary 类型为 AdversarialSummary（非 None）。"""
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        assert result.summary is not None
        assert isinstance(result.summary, AdversarialSummary)

    @pytest.mark.asyncio
    async def test_summary_overall_assessment_non_empty(
        self, mock_llm, config, issue_tree, evidence_index
    ):
        """result.summary.overall_assessment 非空。"""
        engine = RoundEngine(mock_llm, config)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        assert len(result.summary.overall_assessment) >= 1

    @pytest.mark.asyncio
    async def test_default_config_used_when_none(self, mock_llm, issue_tree, evidence_index):
        """不传 config 时使用默认 RoundConfig。"""
        engine = RoundEngine(mock_llm)  # 不传 config
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )
        assert isinstance(result, AdversarialResult)


# ---------------------------------------------------------------------------
# Schemas 单元测试
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_round_config_defaults(self):
        cfg = RoundConfig()
        assert cfg.num_rounds == 3
        assert cfg.max_tokens_per_output == 2000
        assert cfg.max_retries == 3
        assert cfg.temperature == 0.0

    def test_argument_requires_evidence(self):
        from pydantic import ValidationError
        from engines.adversarial.schemas import Argument

        with pytest.raises(ValidationError):
            Argument(
                issue_id="issue-001",
                position="test",
                supporting_evidence_ids=[],  # 空 — 应报错
            )

    def test_adversarial_result_structure(self):
        from engines.adversarial.schemas import AdversarialResult

        result = AdversarialResult(case_id="c-001", run_id="r-001")
        assert result.rounds == []
        assert result.evidence_conflicts == []
        assert result.unresolved_issues == []


# ---------------------------------------------------------------------------
# RoundEngine 基础设施集成测试（WorkspaceManager + JobManager）
# ---------------------------------------------------------------------------


class TestRoundEngineWithInfrastructure:
    @pytest.mark.asyncio
    async def test_outputs_saved_to_workspace(
        self, mock_llm, config, issue_tree, evidence_index, tmp_path
    ):
        """5个 AgentOutput 应通过 WorkspaceManager 持久化到 artifact_index。"""
        from engines.shared.workspace_manager import WorkspaceManager

        ws = WorkspaceManager(tmp_path, CASE_ID)
        ws.init_workspace("civil_loan")

        engine = RoundEngine(mock_llm, config, workspace_manager=ws)
        await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        workspace_data = ws.load_workspace()
        agent_outputs = workspace_data["artifact_index"]["AgentOutput"]
        assert len(agent_outputs) == 5  # 2 claims + 1 ev_manager + 2 rebuttals

    @pytest.mark.asyncio
    async def test_job_lifecycle_completed(
        self, mock_llm, config, issue_tree, evidence_index, tmp_path
    ):
        """job_manager 提供时，job 应完成 created→running→completed 生命周期。"""
        from engines.shared.job_manager import JobManager

        jm = JobManager(tmp_path)
        engine = RoundEngine(mock_llm, config, job_manager=jm)
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        assert result.job_id != ""
        job = jm.load_job(result.job_id)
        assert job is not None
        assert job.job_status.value == "completed"

    @pytest.mark.asyncio
    async def test_no_infrastructure_still_works(
        self, mock_llm, config, issue_tree, evidence_index
    ):
        """不传 workspace_manager 和 job_manager 时仍正常运行（向后兼容）。"""
        engine = RoundEngine(mock_llm, config)  # no infrastructure
        result = await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )
        assert isinstance(result, AdversarialResult)
        assert result.job_id == ""


# ---------------------------------------------------------------------------
# Round 3 并行化验证
# ---------------------------------------------------------------------------


class TestRound3Parallelism:
    """验证 Round 3 原被告 rebuttal 使用 asyncio.gather 并行执行。"""

    @pytest.mark.asyncio
    async def test_round3_rebuttals_run_concurrently(self, config, issue_tree, evidence_index):
        """p_rebuttal 和 d_rebuttal 的开始时间差应 < 单次调用耗时（并行标志）。"""
        import asyncio

        call_start_times: list[float] = []

        class TimedMockLLM:
            """记录每次调用开始时间，模拟 10ms 延迟。"""

            _call_count = 0

            async def create_message(self, *, system: str, user: str, **kwargs) -> str:
                import json

                call_start_times.append(asyncio.get_event_loop().time())
                await asyncio.sleep(0.01)  # 模拟 10ms LLM 延迟
                self._call_count += 1
                # 返回符合格式的固定响应
                return json.dumps(
                    {
                        "title": f"响应 {self._call_count}",
                        "body": "论述内容。",
                        "case_id": CASE_ID,
                        "issue_ids": ["issue-001"],
                        "evidence_citations": ["ev-001"],
                        "risk_flags": [],
                        "arguments": [
                            {
                                "issue_id": "issue-001",
                                "position": "立场",
                                "supporting_evidence_ids": ["ev-001"],
                                "legal_basis": "《民法典》第667条",
                            }
                        ],
                        "conflicts": [],
                    },
                    ensure_ascii=False,
                )

        timed_llm = TimedMockLLM()
        engine = RoundEngine(timed_llm, config)
        await engine.run(
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            plaintiff_party_id=PLAINTIFF_ID,
            defendant_party_id=DEFENDANT_ID,
        )

        # Round 3 是第 3、4 次调用（索引 2 和 3）；Round 1 p_claim、d_claim 是第 1、2 次
        # Round 2 ev 是第 3 次，Round 3 p_rebuttal/d_rebuttal 是第 4、5 次
        # 实际调用顺序：r1_p, r1_d, r2_ev, r3_p+r3_d (并行), summarizer
        assert len(call_start_times) >= 5, f"期望 ≥5 次调用，实际 {len(call_start_times)}"

        # 找到 Round 3 的两次 rebuttal 调用（第 4、5 次，索引 3 和 4）
        r3_p_start = call_start_times[3]
        r3_d_start = call_start_times[4]
        # 并行时两者开始时间差 < 单次延迟 (0.01s)
        time_diff = abs(r3_d_start - r3_p_start)
        assert time_diff < 0.009, (
            f"Round 3 rebuttals 应并行执行，开始时间差 {time_diff:.4f}s ≥ 0.009s（串行特征）"
        )
