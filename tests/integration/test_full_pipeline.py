"""
端到端集成测试 — 全链路六引擎串联。
End-to-end integration tests — full six-engine pipeline.

覆盖路径 / Coverage:
1. test_full_pipeline_happy_path          — 完整六引擎串联 happy path
2. test_evidence_to_issue_data_compat     — Evidence→dict 适配层兼容性
3. test_evidence_index_construction       — EvidenceIndex 构建后被 ReportGenerator 消费
4. test_simulation_run_issue_id_consistency — ScenarioSimulator affected_issue_ids 一致性
5. test_multi_turn_followup_after_report  — 两轮追问，previous_turns 正确传递
6. test_procedure_planner_failure_degradation — ProcedurePlanner LLM 失败降级
"""

from __future__ import annotations

import json

import pytest

from engines.case_structuring.evidence_indexer.indexer import EvidenceIndexer
from engines.case_structuring.issue_extractor.extractor import IssueExtractor
from engines.interactive_followup.responder import FollowupResponder
from engines.procedure_setup.planner import ProcedurePlanner
from engines.procedure_setup.schemas import PartyInfo, ProcedureSetupInput
from engines.report_generation.generator import ReportGenerator
from engines.shared.models import EvidenceIndex
from engines.simulation_run.schemas import ChangeItem, ChangeItemObjectType, ScenarioInput
from engines.simulation_run.simulator import ScenarioSimulator

from .conftest import (
    CASE_ID,
    CASE_SLUG,
    WORKSPACE_ID,
    MockLLMClient,
    SequentialMockLLMClient,
)


# ---------------------------------------------------------------------------
# Mock LLM 响应数据 / Mock LLM response payloads
# 每个引擎一份，数据 ID 在链路间保持一致。
# One payload per engine; IDs are consistent across the pipeline.
# ---------------------------------------------------------------------------

# ── EvidenceIndexer：返回数组 ────────────────────────────────────────────────
# 产出 evidence_id: evidence-integ-001-001 / evidence-integ-001-002
_EVIDENCE_INDEXER_RESPONSE = json.dumps(
    [
        {
            "title": "借条原件",
            "summary": "被告李某于2024年1月15日出具借条，载明借款本金50万元、年利率6%",
            "evidence_type": "documentary",
            "source_id": "mat-integ-001",  # 必须与 RawMaterial.source_id 一致（source_coverage 校验）
            "target_facts": ["fact-integ-001-loan-agreement", "fact-integ-001-loan-amount"],
            "target_issues": [],
        },
        {
            "title": "银行转账电子回单",
            "summary": "工商银行电子回单显示原告张某于2024年1月15日向被告李某转账500,000元",
            "evidence_type": "electronic_data",
            "source_id": "mat-integ-002",
            "target_facts": ["fact-integ-001-loan-disbursement"],
            "target_issues": [],
        },
    ],
    ensure_ascii=False,
)

# ── IssueExtractor：返回对象 ─────────────────────────────────────────────────
# 引用 evidence_id 必须与 EvidenceIndexer 输出一致
_ISSUE_EXTRACTOR_RESPONSE = json.dumps(
    {
        "issues": [
            {
                "tmp_id": "issue-tmp-001",
                "title": "借贷关系成立",
                "issue_type": "factual",
                "parent_tmp_id": None,
                "related_claim_ids": ["claim-integ-001-01", "claim-integ-001-02"],
                "related_defense_ids": [],
                "evidence_ids": [
                    "evidence-integ-001-001",
                    "evidence-integ-001-002",
                ],
                "fact_propositions": [
                    {
                        "text": "双方存在合法有效的借贷合意，且款项已实际交付",
                        "status": "supported",
                        "linked_evidence_ids": [
                            "evidence-integ-001-001",
                            "evidence-integ-001-002",
                        ],
                    }
                ],
            },
            {
                "tmp_id": "issue-tmp-002",
                "title": "还款义务及金额",
                "issue_type": "factual",
                "parent_tmp_id": "issue-tmp-001",
                "related_claim_ids": ["claim-integ-001-01"],
                "related_defense_ids": ["defense-integ-001-01"],
                "evidence_ids": ["evidence-integ-001-002"],
                "fact_propositions": [
                    {
                        "text": "被告是否已部分归还借款本金尚存争议",
                        "status": "disputed",
                        "linked_evidence_ids": ["evidence-integ-001-002"],
                    }
                ],
            },
        ],
        "burdens": [
            {
                "issue_tmp_id": "issue-tmp-001",
                "burden_party_id": "party-plaintiff-001",
                "description": "原告应证明借贷关系成立，包括借贷合意和款项实际交付",
                "proof_standard": "高度盖然性",
                "legal_basis": "《最高人民法院关于审理民间借贷案件适用法律若干问题的规定》第二条",
            }
        ],
        "claim_issue_mapping": [
            {
                "claim_id": "claim-integ-001-01",
                "issue_tmp_ids": ["issue-tmp-001", "issue-tmp-002"],
            },
            {
                "claim_id": "claim-integ-001-02",
                "issue_tmp_ids": ["issue-tmp-001"],
            },
        ],
        "defense_issue_mapping": [
            {
                "defense_id": "defense-integ-001-01",
                "issue_tmp_ids": ["issue-tmp-002"],
            }
        ],
    },
    ensure_ascii=False,
)

# ── ProcedurePlanner：返回对象 ────────────────────────────────────────────────
# 只提供两个阶段，其余由引擎用默认配置补全（共8个）
_PROCEDURE_PLANNER_RESPONSE = json.dumps(
    {
        "procedure_states": [
            {
                "phase": "case_intake",
                "allowed_role_codes": ["plaintiff_agent", "judge_agent", "evidence_manager"],
                "readable_access_domains": ["shared_common"],
                "writable_object_types": ["Party", "Claim", "Evidence"],
                "admissible_evidence_statuses": ["private"],
                "entry_conditions": ["案件登记完成", "原告起诉状已接收"],
                "exit_conditions": ["被告已收到应诉通知", "双方当事人身份核实完毕"],
            },
            {
                "phase": "element_mapping",
                "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
                "readable_access_domains": ["shared_common"],
                "writable_object_types": ["Issue", "Burden", "Claim", "Defense"],
                "admissible_evidence_statuses": ["private", "submitted"],
                "entry_conditions": ["案件受理完毕"],
                "exit_conditions": ["争点树梳理完成", "举证责任分配明确"],
            },
        ],
        "procedure_config": {
            "evidence_submission_deadline_days": 15,
            "evidence_challenge_window_days": 10,
            "max_rounds_per_phase": 3,
            "applicable_laws": ["《中华人民共和国民法典》", "《民事诉讼法》"],
        },
        "timeline_events": [
            {
                "event_type": "evidence_submission_deadline",
                "phase": "evidence_submission",
                "description": "举证期限届满",
                "relative_day": 15,
                "is_mandatory": True,
            },
            {
                "event_type": "evidence_challenge_deadline",
                "phase": "evidence_challenge",
                "description": "质证期限届满",
                "relative_day": 25,
                "is_mandatory": True,
            },
        ],
    },
    ensure_ascii=False,
)

# ── ReportGenerator：返回对象 ─────────────────────────────────────────────────
# linked_evidence_ids 和 supporting_evidence_ids 必须与 EvidenceIndexer 输出的 ID 一致
_REPORT_GENERATOR_RESPONSE = json.dumps(
    {
        "title": "民间借贷纠纷诊断报告（集成测试）",
        "summary": (
            "本案为民间借贷纠纷。原告张某起诉被告李某归还借款50万元及逾期利息。"
            "借贷关系通过借条和银行转账记录证明成立，举证责任已履行。"
        ),
        "sections": [
            {
                "title": "借贷关系成立认定",
                "body": (
                    "原告提供借条原件（evidence-integ-001-001）证明借贷合意，"
                    "银行转账回单（evidence-integ-001-002）证明款项实际交付。"
                    "两份证据相互印证，借贷关系可认定成立，原告举证责任已履行。"
                ),
                "linked_issue_ids": ["issue-integ-001-001"],
                "linked_evidence_ids": [
                    "evidence-integ-001-001",
                    "evidence-integ-001-002",
                ],
                "key_conclusions": [
                    {
                        "text": "借贷关系依据借条和转账记录可认定成立，原告举证责任已履行",
                        "statement_class": "fact",
                        "supporting_evidence_ids": [
                            "evidence-integ-001-001",
                            "evidence-integ-001-002",
                        ],
                    }
                ],
            },
        ],
    },
    ensure_ascii=False,
)

# ── ScenarioSimulator：返回对象 ───────────────────────────────────────────────
# diff_entries 中的 issue_id 必须与 IssueTree 中已知的 issue_id 一致
_SCENARIO_SIMULATOR_RESPONSE = json.dumps(
    {
        "summary": "借条降级为复印件后对借贷关系争点产生削弱影响",
        "diff_entries": [
            {
                "issue_id": "issue-integ-001-001",
                "impact_description": (
                    "借条由原件变为复印件（原件遗失），真实性待核实，"
                    "削弱原告证明借贷关系成立的核心证据效力"
                ),
                "direction": "weaken",
            }
        ],
    },
    ensure_ascii=False,
)

# ── FollowupResponder：两轮各一份 ──────────────────────────────────────────────
# evidence_ids 和 issue_ids 必须是报告已引用集合的子集
_FOLLOWUP_TURN1_RESPONSE = json.dumps(
    {
        "answer": (
            "根据借条原件（evidence-integ-001-001）和银行转账回单（evidence-integ-001-002），"
            "借贷关系可认定成立。两份证据相互印证，具有较强的证明力。"
        ),
        "issue_ids": ["issue-integ-001-001"],
        "evidence_ids": ["evidence-integ-001-001", "evidence-integ-001-002"],
        "statement_class": "fact",
        "citations": [
            {"evidence_id": "evidence-integ-001-001", "quote": "借款本金50万元，年利率6%"},
            {"evidence_id": "evidence-integ-001-002", "quote": "转账金额500,000.00元"},
        ],
    },
    ensure_ascii=False,
)

_FOLLOWUP_TURN2_RESPONSE = json.dumps(
    {
        "answer": (
            "被告抗辩已归还20万元，但其并未提供独立的还款凭证。"
            "转账回单（evidence-integ-001-002）仅记录原告向被告的借款汇款，"
            "不能证明被告已还款，被告举证责任未履行。"
        ),
        "issue_ids": ["issue-integ-001-001"],
        "evidence_ids": ["evidence-integ-001-002"],
        "statement_class": "inference",
        "citations": [
            {"evidence_id": "evidence-integ-001-002", "quote": "转账方向为原告到被告"},
        ],
    },
    ensure_ascii=False,
)


# ---------------------------------------------------------------------------
# 辅助函数：构建前置数据（避免重复代码）
# ---------------------------------------------------------------------------


async def _build_evidences(sample_materials):
    """运行 EvidenceIndexer，返回 list[Evidence]。"""
    return await EvidenceIndexer(
        llm_client=MockLLMClient(_EVIDENCE_INDEXER_RESPONSE),
        case_type="civil_loan",
    ).index(
        materials=sample_materials,
        case_id=CASE_ID,
        owner_party_id="party-plaintiff-001",
        case_slug=CASE_SLUG,
    )


async def _build_issue_tree(evidences, sample_claims, sample_defenses):
    """运行 IssueExtractor，返回 IssueTree。"""
    return await IssueExtractor(
        llm_client=MockLLMClient(_ISSUE_EXTRACTOR_RESPONSE),
        case_type="civil_loan",
    ).extract(
        claims=sample_claims,
        defenses=sample_defenses,
        evidence=[e.model_dump() for e in evidences],  # 适配层
        case_id=CASE_ID,
        case_slug=CASE_SLUG,
    )


async def _build_report(issue_tree, evidence_index):
    """运行 ReportGenerator，返回 ReportArtifact。"""
    return await ReportGenerator(
        llm_client=MockLLMClient(_REPORT_GENERATOR_RESPONSE),
        case_type="civil_loan",
    ).generate(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        run_id="run-report-helper-001",
        report_slug="integ-001",
    )


# ---------------------------------------------------------------------------
# 测试 1：完整六引擎串联 happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_happy_path(sample_materials, sample_claims, sample_defenses):
    """完整六引擎串联：每步输出能正确作为下一步输入，且各合约不变量均成立。
    Full six-engine chain: each output feeds correctly into the next engine,
    and all contract invariants hold.
    """
    # ── Step 1: EvidenceIndexer → list[Evidence] ─────────────────────────
    evidences = await _build_evidences(sample_materials)

    assert len(evidences) == 2
    # 确定性 ID（case_slug="integ-001"，索引从1开始）
    assert evidences[0].evidence_id == "evidence-integ-001-001"
    assert evidences[1].evidence_id == "evidence-integ-001-002"
    # 合约：初始状态必须为 private / owner_private
    for ev in evidences:
        assert ev.status.value == "private"
        assert ev.access_domain.value == "owner_private"

    # ── Step 2: IssueExtractor → IssueTree ───────────────────────────────
    # 适配层：Evidence → list[dict]（model_dump 保留 evidence_id 字段名）
    issue_tree = await _build_issue_tree(evidences, sample_claims, sample_defenses)

    assert issue_tree.case_id == CASE_ID
    assert len(issue_tree.issues) == 2
    assert len(issue_tree.burdens) >= 1

    # 验证 IssueExtractor 正确消费了 EvidenceIndexer 的 evidence_id
    root_issue = next(i for i in issue_tree.issues if i.parent_issue_id is None)
    assert "evidence-integ-001-001" in root_issue.evidence_ids
    assert "evidence-integ-001-002" in root_issue.evidence_ids

    # 验证 issue_id 格式（确定性生成）
    issue_ids = {i.issue_id for i in issue_tree.issues}
    assert "issue-integ-001-001" in issue_ids
    assert "issue-integ-001-002" in issue_ids

    # ── Step 3: ProcedurePlanner → ProcedureSetupResult ──────────────────
    setup_input = ProcedureSetupInput(
        workspace_id=WORKSPACE_ID,
        case_id=CASE_ID,
        case_type="civil_loan",
        parties=[
            PartyInfo(
                party_id="party-plaintiff-001",
                name="张三",
                role_code="plaintiff_agent",
                side="plaintiff",
            ),
            PartyInfo(
                party_id="party-defendant-001",
                name="李四",
                role_code="defendant_agent",
                side="defendant",
            ),
        ],
    )
    procedure_result = await ProcedurePlanner(
        llm_client=MockLLMClient(_PROCEDURE_PLANNER_RESPONSE),
        case_type="civil_loan",
    ).plan(
        setup_input=setup_input,
        issue_tree=issue_tree,
        run_id="run-procedure-001",
    )

    assert procedure_result.run.status == "completed"
    assert procedure_result.run.trigger_type == "procedure_setup"
    # 合约：覆盖全部 8 个法律程序阶段
    assert len(procedure_result.procedure_states) == 8

    # 合约：judge_questions 阶段不能读取 owner_private
    judge_q = next(
        s for s in procedure_result.procedure_states if s.phase == "judge_questions"
    )
    assert "owner_private" not in judge_q.readable_access_domains

    # 合约：output_branching 仅允许 admitted_for_discussion
    output_branch = next(
        s for s in procedure_result.procedure_states if s.phase == "output_branching"
    )
    assert output_branch.admissible_evidence_statuses == ["admitted_for_discussion"]

    # ── Step 4: ReportGenerator → ReportArtifact ─────────────────────────
    # 适配层：list[Evidence] → EvidenceIndex
    evidence_index = EvidenceIndex(case_id=CASE_ID, evidence=evidences)

    report = await ReportGenerator(
        llm_client=MockLLMClient(_REPORT_GENERATOR_RESPONSE),
        case_type="civil_loan",
    ).generate(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        run_id="run-report-001",
        report_slug="integ-001",
    )

    assert report.case_id == CASE_ID
    assert len(report.sections) >= 1

    # 合约：citation_completeness — 每条 key_conclusion 至少一个 supporting_evidence_id
    for section in report.sections:
        for conclusion in section.key_conclusions:
            assert len(conclusion.supporting_evidence_ids) >= 1, (
                f"结论 {conclusion.conclusion_id} 缺少 supporting_evidence_id"
            )

    # ── Step 5: ScenarioSimulator → ScenarioResult ────────────────────────
    scenario_input = ScenarioInput(
        scenario_id="scenario-integ-evidence-downgrade-001",
        baseline_run_id="run-procedure-001",
        change_set=[
            ChangeItem(
                target_object_type=ChangeItemObjectType.Evidence,
                target_object_id="evidence-integ-001-001",
                field_path="admissibility_notes",
                old_value=None,
                new_value="借条为复印件，原件遗失，真实性存疑",
            )
        ],
        workspace_id=WORKSPACE_ID,
    )
    scenario_result = await ScenarioSimulator(
        llm_client=MockLLMClient(_SCENARIO_SIMULATOR_RESPONSE),
        case_type="civil_loan",
    ).simulate(
        scenario_input=scenario_input,
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        run_id="run-scenario-001",
    )

    assert scenario_result.scenario.case_id == CASE_ID
    assert scenario_result.scenario.status.value == "completed"
    assert scenario_result.run.trigger_type == "scenario_execution"
    assert len(scenario_result.scenario.diff_summary) >= 1

    # ── Step 6: FollowupResponder → InteractionTurn ───────────────────────
    turn = await FollowupResponder(
        llm_client=MockLLMClient(_FOLLOWUP_TURN1_RESPONSE),
        case_type="civil_loan",
    ).respond(
        report=report,
        question="借贷关系是否确实成立？请基于证据详细说明。",
        turn_slug="integ-001",
        run_id="run-report-001",
    )

    assert turn.case_id == CASE_ID
    assert turn.report_id == report.report_id
    assert turn.answer
    # 合约：issue_ids 非空
    assert len(turn.issue_ids) >= 1
    # 合约：evidence_ids ⊆ 报告已引用证据
    report_evidence_ids = {
        eid
        for sec in report.sections
        for eid in sec.linked_evidence_ids
    }
    for eid in turn.evidence_ids:
        assert eid in report_evidence_ids, f"追问回答引用了报告范围外的 evidence_id: {eid}"


# ---------------------------------------------------------------------------
# 测试 2：Evidence → dict 适配层兼容性
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_to_issue_data_compat(sample_materials, sample_claims, sample_defenses):
    """验证 Evidence.model_dump() 格式被 IssueExtractor 正确消费，且 evidence_id 字段名保留。
    Verifies Evidence.model_dump() format is correctly consumed by IssueExtractor,
    with 'evidence_id' field name preserved.
    """
    evidences = await _build_evidences(sample_materials)
    evidence_dicts = [e.model_dump() for e in evidences]

    # model_dump() 必须保留 Pydantic 字段名（不能变成 'id' 等）
    for d in evidence_dicts:
        assert "evidence_id" in d, "model_dump() 应保留 'evidence_id' 字段名"
        assert "case_id" in d
        assert "owner_party_id" in d
        assert "evidence_type" in d
        # 枚举值应序列化为字符串
        assert isinstance(d["evidence_type"], str), "EvidenceType 枚举应序列化为字符串"
        assert isinstance(d["status"], str), "EvidenceStatus 枚举应序列化为字符串"

    # IssueExtractor 能正确消费 evidence_dicts
    issue_tree = await IssueExtractor(
        llm_client=MockLLMClient(_ISSUE_EXTRACTOR_RESPONSE),
        case_type="civil_loan",
    ).extract(
        claims=sample_claims,
        defenses=sample_defenses,
        evidence=evidence_dicts,
        case_id=CASE_ID,
        case_slug=CASE_SLUG,
    )

    assert len(issue_tree.issues) > 0

    # 核心合约：IssueExtractor 引用的 evidence_id 必须来自输入（零悬空引用）
    known_ids = {d["evidence_id"] for d in evidence_dicts}
    for issue in issue_tree.issues:
        for eid in issue.evidence_ids:
            assert eid in known_ids, (
                f"issue '{issue.issue_id}' 引用了未知 evidence_id: {eid}"
            )
        for fp in issue.fact_propositions:
            for eid in fp.linked_evidence_ids:
                assert eid in known_ids, (
                    f"FactProposition 引用了未知 evidence_id: {eid}"
                )


# ---------------------------------------------------------------------------
# 测试 3：EvidenceIndex 构建后被 ReportGenerator 消费
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_index_construction(sample_materials, sample_claims, sample_defenses):
    """验证从 list[Evidence] 手动构建 EvidenceIndex 后，ReportGenerator 零悬空引用。
    Verifies zero dangling references in ReportGenerator output when EvidenceIndex
    is manually constructed from list[Evidence].
    """
    evidences = await _build_evidences(sample_materials)
    issue_tree = await _build_issue_tree(evidences, sample_claims, sample_defenses)

    # 适配层：list[Evidence] → EvidenceIndex
    evidence_index = EvidenceIndex(case_id=CASE_ID, evidence=evidences)

    assert evidence_index.case_id == CASE_ID
    assert len(evidence_index.evidence) == len(evidences)

    report = await ReportGenerator(
        llm_client=MockLLMClient(_REPORT_GENERATOR_RESPONSE),
        case_type="civil_loan",
    ).generate(
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        run_id="run-report-compat-001",
        report_slug="compat-001",
    )

    assert report.case_id == CASE_ID
    assert len(report.sections) >= 1

    # 零悬空引用：报告引用的所有 evidence_id 必须在 EvidenceIndex 中存在
    known_ids = {e.evidence_id for e in evidence_index.evidence}
    for section in report.sections:
        for eid in section.linked_evidence_ids:
            assert eid in known_ids, f"章节引用了悬空 evidence_id: {eid}"
        for conclusion in section.key_conclusions:
            for eid in conclusion.supporting_evidence_ids:
                assert eid in known_ids, f"结论引用了悬空 evidence_id: {eid}"

    # 合约：所有顶层 Issue 均被覆盖（ReportGenerator 会自动补全缺失章节）
    root_issue_ids = {
        i.issue_id for i in issue_tree.issues if i.parent_issue_id is None
    }
    covered_issue_ids = {
        iid for sec in report.sections for iid in sec.linked_issue_ids
    }
    assert root_issue_ids.issubset(covered_issue_ids), (
        f"未覆盖的顶层争点: {root_issue_ids - covered_issue_ids}"
    )


# ---------------------------------------------------------------------------
# 测试 4：ScenarioSimulator affected_issue_ids 与 IssueTree 一致性
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulation_run_issue_id_consistency(sample_materials, sample_claims, sample_defenses):
    """验证 ScenarioSimulator.affected_issue_ids ⊆ IssueTree.issues[*].issue_id。
    Verifies affected_issue_ids is a subset of known issue IDs from the IssueTree.
    """
    evidences = await _build_evidences(sample_materials)
    issue_tree = await _build_issue_tree(evidences, sample_claims, sample_defenses)
    evidence_index = EvidenceIndex(case_id=CASE_ID, evidence=evidences)

    scenario_result = await ScenarioSimulator(
        llm_client=MockLLMClient(_SCENARIO_SIMULATOR_RESPONSE),
        case_type="civil_loan",
    ).simulate(
        scenario_input=ScenarioInput(
            scenario_id="scenario-integ-consistency-001",
            baseline_run_id="run-baseline-001",
            change_set=[
                ChangeItem(
                    target_object_type=ChangeItemObjectType.Evidence,
                    target_object_id="evidence-integ-001-001",
                    field_path="admissibility_notes",
                    old_value=None,
                    new_value="复印件，真实性存疑",
                )
            ],
            workspace_id=WORKSPACE_ID,
        ),
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        run_id="run-scenario-consistency-001",
    )

    assert scenario_result.run.status == "completed"
    assert scenario_result.run.trigger_type == "scenario_execution"

    known_issue_ids = {i.issue_id for i in issue_tree.issues}

    # 合约：affected_issue_ids ⊆ IssueTree 已知 issue_id
    for iid in scenario_result.scenario.affected_issue_ids:
        assert iid in known_issue_ids, (
            f"affected_issue_ids 包含未知 issue_id: {iid}"
        )

    # 合约：diff_summary 中每条 DiffEntry 的 issue_id 均在 IssueTree 中
    diff_summary = scenario_result.scenario.diff_summary
    assert isinstance(diff_summary, list)
    for entry in diff_summary:
        assert entry.issue_id in known_issue_ids, (
            f"diff_entry 引用了未知 issue_id: {entry.issue_id}"
        )
        assert entry.impact_description, "impact_description 不能为空"
        assert entry.direction is not None

    # 合约：baseline anchor — change_set 为空时拒绝执行
    with pytest.raises(ValueError, match="baseline anchor"):
        await ScenarioSimulator(
            llm_client=MockLLMClient(_SCENARIO_SIMULATOR_RESPONSE),
            case_type="civil_loan",
        ).simulate(
            scenario_input=ScenarioInput(
                scenario_id="scenario-baseline",
                baseline_run_id="run-baseline-001",
                change_set=[],  # 空 change_set — baseline anchor，应拒绝
                workspace_id=WORKSPACE_ID,
            ),
            issue_tree=issue_tree,
            evidence_index=evidence_index,
            run_id="run-baseline-guard-001",
        )


# ---------------------------------------------------------------------------
# 测试 5：两轮追问，previous_turns 正确传递
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_turn_followup_after_report(sample_materials, sample_claims, sample_defenses):
    """验证两轮追问：
    - 第二轮 previous_turns 正确传入（体现在 LLM user prompt 中）
    - issue_ids 始终非空
    - turn_index 递增
    Verifies two-turn follow-up: previous_turns passed correctly on turn 2,
    issue_ids always non-empty, turn_index increments.
    """
    evidences = await _build_evidences(sample_materials)
    issue_tree = await _build_issue_tree(evidences, sample_claims, sample_defenses)
    evidence_index = EvidenceIndex(case_id=CASE_ID, evidence=evidences)
    report = await _build_report(issue_tree, evidence_index)

    # 使用 SequentialMockLLMClient：第一次调用返回 turn1 响应，第二次返回 turn2 响应
    sequential_client = SequentialMockLLMClient(
        [_FOLLOWUP_TURN1_RESPONSE, _FOLLOWUP_TURN2_RESPONSE]
    )
    responder = FollowupResponder(
        llm_client=sequential_client,
        case_type="civil_loan",
    )

    # ── 第一轮追问 / Turn 1 ───────────────────────────────────────────────
    turn_1 = await responder.respond(
        report=report,
        question="借贷关系是否确实成立？请基于证据详细说明。",
        turn_slug="multiturn-001",
        run_id="run-report-helper-001",
    )

    assert turn_1.case_id == CASE_ID
    assert turn_1.report_id == report.report_id
    assert len(turn_1.issue_ids) >= 1
    assert turn_1.answer
    assert turn_1.turn_index == 1  # 第一轮，index=1

    # ── 第二轮追问（传入第一轮作为 previous_turns）/ Turn 2 ───────────────
    turn_2 = await responder.respond(
        report=report,
        question="被告的还款抗辩是否有证据支撑？",
        previous_turns=[turn_1],
        turn_slug="multiturn-001",
        run_id="run-report-helper-001",
    )

    assert sequential_client.call_count == 2

    assert turn_2.case_id == CASE_ID
    assert turn_2.report_id == report.report_id
    assert len(turn_2.issue_ids) >= 1
    assert turn_2.answer
    assert turn_2.turn_index == 2  # 第二轮，index=2

    # 验证第二轮的 user prompt 包含第一轮的追问内容（history 传入）
    assert sequential_client.last_user is not None
    assert turn_1.question in sequential_client.last_user, (
        "第二轮 LLM 调用的 user prompt 应包含第一轮的追问问题"
    )

    # 合约：evidence_ids ⊆ 报告已引用证据
    report_evidence_ids = {
        eid for sec in report.sections for eid in sec.linked_evidence_ids
    }
    for turn in [turn_1, turn_2]:
        for eid in turn.evidence_ids:
            assert eid in report_evidence_ids, (
                f"turn {turn.turn_index} 引用了报告范围外的 evidence_id: {eid}"
            )


# ---------------------------------------------------------------------------
# 测试 6：ProcedurePlanner LLM 失败降级
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_procedure_planner_failure_degradation(sample_materials, sample_claims, sample_defenses):
    """验证 ProcedurePlanner LLM 持续失败时：
    - 不抛出异常（plan() 内部捕获）
    - 返回 run.status = "failed"
    - 仍返回完整 8 个程序状态（使用默认配置）
    - 访问控制约束在默认配置中同样成立
    Verifies that ProcedurePlanner degrades gracefully on LLM failure:
    - No exception raised (caught internally by plan())
    - Returns run.status = "failed"
    - Still returns 8 procedure states using default config
    - Access control constraints still enforced in default config
    """
    evidences = await _build_evidences(sample_materials)
    issue_tree = await _build_issue_tree(evidences, sample_claims, sample_defenses)

    # LLM 持续失败（fail_times=10 > max_retries=3）
    failing_client = MockLLMClient("", fail_times=10)

    planner = ProcedurePlanner(
        llm_client=failing_client,
        case_type="civil_loan",
        max_retries=3,
    )

    setup_input = ProcedureSetupInput(
        workspace_id=WORKSPACE_ID,
        case_id=CASE_ID,
        case_type="civil_loan",
        parties=[
            PartyInfo(
                party_id="party-plaintiff-001",
                name="张三",
                role_code="plaintiff_agent",
                side="plaintiff",
            ),
        ],
    )

    # plan() 不应抛出异常（内部捕获所有 LLM / 解析错误）
    procedure_result = await planner.plan(
        setup_input=setup_input,
        issue_tree=issue_tree,
        run_id="run-failed-001",
    )

    # 合约：失败时 run.status = "failed"
    assert procedure_result.run.status == "failed"
    assert procedure_result.run.trigger_type == "procedure_setup"

    # 合约：失败时仍返回完整 8 个程序状态（使用默认配置，不中断下游）
    assert len(procedure_result.procedure_states) == 8

    phases = [s.phase for s in procedure_result.procedure_states]
    assert "case_intake" in phases
    assert "output_branching" in phases

    # 合约：访问控制约束在 fallback 默认配置中同样成立
    judge_q = next(
        s for s in procedure_result.procedure_states if s.phase == "judge_questions"
    )
    assert "owner_private" not in judge_q.readable_access_domains, (
        "judge_questions 阶段即使在 fallback 配置中也不能读取 owner_private"
    )

    output_branch = next(
        s for s in procedure_result.procedure_states if s.phase == "output_branching"
    )
    assert output_branch.admissible_evidence_statuses == ["admitted_for_discussion"], (
        "output_branching 阶段即使在 fallback 配置中也只能使用 admitted_for_discussion"
    )

    # LLM 客户端应被调用过（max_retries=3: 1次初始调用 + 3次重试 = 4次总调用）
    assert failing_client.call_count == 4
