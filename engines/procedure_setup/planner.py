"""
程序设置引擎核心模块
Procedure setup engine core module.

根据案件类型（case_type）、当事人信息（parties）和争点树（IssueTree），
通过 LLM 生成结构化程序状态序列（ProcedureState[]）、程序配置和时间线事件。
Generates a structured ProcedureState sequence, config, and timeline events
from case_type, parties, and IssueTree via LLM.

合约保证 / Contract guarantees:
- procedure_states 覆盖全部八个法律程序阶段
- judge_questions 阶段不读取 owner_private
- output_branching 阶段仅基于 admitted_for_discussion 证据
- state_id 由引擎确定性生成，不依赖 LLM
- next_state_ids 按阶段顺序确定性生成
- trigger_type 固定为 "procedure_setup"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .schemas import (
    ArtifactRef,
    InputSnapshot,
    IssueTree,
    LLMProcedureConfig,
    LLMProcedureOutput,
    LLMProcedureState,
    MaterialRef,
    PHASE_ORDER,
    ProcedureConfig,
    ProcedureSetupInput,
    ProcedureSetupResult,
    ProcedureState,
    Run,
    TimelineEvent,
)

# tool_use JSON Schema（模块加载时计算一次）
_TOOL_SCHEMA: dict = LLMProcedureOutput.model_json_schema()


# ---------------------------------------------------------------------------
# 工具函数 / Utility functions
# ---------------------------------------------------------------------------


def _make_state_id(case_id: str, phase: str) -> str:
    """生成确定性 state_id。
    Generate a deterministic state_id from case_id and phase.

    格式 / Format: pstate-{case_id}-{phase}-001
    """
    return f"pstate-{case_id}-{phase}-001"


def _build_next_state_ids(case_id: str, phase: str) -> list[str]:
    """根据阶段顺序生成 next_state_ids（终止阶段返回空列表）。
    Build next_state_ids based on phase order (returns [] for terminal phase).
    """
    try:
        idx = PHASE_ORDER.index(phase)
    except ValueError:
        return []
    if idx + 1 < len(PHASE_ORDER):
        next_phase = PHASE_ORDER[idx + 1]
        return [_make_state_id(case_id, next_phase)]
    # 终止阶段（output_branching）/ Terminal phase
    return []


def _sanitize_access_domains(domains: list[str], phase: str) -> list[str]:
    """清理访问域列表，强制执行 judge_questions 约束。
    Sanitize access domain list, enforcing judge_questions constraint.

    judge_questions 阶段必须移除 owner_private。
    owner_private must be removed from judge_questions phase.
    """
    if phase == "judge_questions":
        return [d for d in domains if d != "owner_private"]
    return domains


def _sanitize_evidence_statuses(statuses: list[str], phase: str) -> list[str]:
    """清理证据状态列表，强制执行 output_branching 约束。
    Sanitize evidence status list, enforcing output_branching constraint.

    output_branching 阶段只允许 admitted_for_discussion。
    output_branching phase only allows admitted_for_discussion.
    """
    if phase == "output_branching":
        return ["admitted_for_discussion"]
    return statuses


# ---------------------------------------------------------------------------
# 默认程序状态数据（当 LLM 无有效输出时使用）
# Default procedure state data (used when LLM returns no valid output)
# ---------------------------------------------------------------------------

_DEFAULT_PHASE_CONFIG: dict[str, dict] = {
    "case_intake": {
        "allowed_role_codes": ["plaintiff_agent", "judge_agent", "evidence_manager"],
        "readable_access_domains": ["shared_common"],
        "writable_object_types": ["Party", "Claim", "Evidence"],
        "admissible_evidence_statuses": ["private"],
        "entry_conditions": ["案件登记完成", "原告起诉状已接收"],
        "exit_conditions": ["被告已收到应诉通知", "双方当事人身份核实完毕"],
    },
    "element_mapping": {
        "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
        "readable_access_domains": ["shared_common"],
        "writable_object_types": ["Issue", "Burden", "Claim", "Defense"],
        "admissible_evidence_statuses": ["private", "submitted"],
        "entry_conditions": ["案件受理完毕"],
        "exit_conditions": ["争点树梳理完成", "举证责任分配明确"],
    },
    "opening": {
        "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
        "readable_access_domains": ["shared_common"],
        "writable_object_types": ["Claim", "Defense", "AgentOutput"],
        "admissible_evidence_statuses": ["submitted"],
        "entry_conditions": ["争点梳理完成"],
        "exit_conditions": ["原告陈述意见完毕", "被告陈述意见完毕"],
    },
    "evidence_submission": {
        "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "evidence_manager"],
        "readable_access_domains": ["shared_common"],
        "writable_object_types": ["Evidence", "AgentOutput"],
        "admissible_evidence_statuses": ["private", "submitted"],
        "entry_conditions": ["举证期限已开始"],
        "exit_conditions": ["举证期限届满", "双方证据均已提交"],
    },
    "evidence_challenge": {
        "allowed_role_codes": [
            "plaintiff_agent",
            "defendant_agent",
            "evidence_manager",
            "judge_agent",
        ],
        "readable_access_domains": ["shared_common", "admitted_record"],
        "writable_object_types": ["Evidence", "AgentOutput"],
        "admissible_evidence_statuses": ["submitted", "challenged"],
        "entry_conditions": ["举证期限届满"],
        "exit_conditions": ["质证程序完毕", "争议证据状态确定"],
    },
    "judge_questions": {
        "allowed_role_codes": ["judge_agent"],
        "readable_access_domains": ["shared_common", "admitted_record"],
        "writable_object_types": ["AgentOutput"],
        "admissible_evidence_statuses": ["admitted_for_discussion"],
        "entry_conditions": ["质证程序完毕"],
        "exit_conditions": ["法官问询完毕", "当事人问题已回复"],
    },
    "rebuttal": {
        "allowed_role_codes": ["plaintiff_agent", "defendant_agent", "judge_agent"],
        "readable_access_domains": ["shared_common", "admitted_record"],
        "writable_object_types": ["AgentOutput"],
        "admissible_evidence_statuses": ["admitted_for_discussion"],
        "entry_conditions": ["法官问询完毕"],
        "exit_conditions": ["双方辩论意见完毕"],
    },
    "output_branching": {
        "allowed_role_codes": ["judge_agent", "review_agent"],
        "readable_access_domains": ["shared_common", "admitted_record"],
        "writable_object_types": ["AgentOutput", "ReportArtifact"],
        "admissible_evidence_statuses": ["admitted_for_discussion"],
        "entry_conditions": ["辩论终结"],
        "exit_conditions": ["结论性意见生成完毕", "争点处理结果输出"],
    },
}


# ---------------------------------------------------------------------------
# 主引擎类 / Main engine class
# ---------------------------------------------------------------------------


class ProcedurePlanner:
    """程序设置规划器
    Procedure Planner.

    输入 ProcedureSetupInput + IssueTree，输出 ProcedureSetupResult。
    Takes ProcedureSetupInput + IssueTree, outputs a ProcedureSetupResult.

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
        setup_input: ProcedureSetupInput,
        issue_tree: IssueTree,
    ) -> None:
        """验证输入数据合法性。
        Validate input data validity.

        Raises:
            ValueError: issues 为空、case_id 不匹配时。
                        Empty issues or case_id mismatch.
        """
        if not issue_tree.issues:
            raise ValueError("issue_tree.issues 不能为空 / issue_tree.issues cannot be empty")
        if setup_input.case_id != issue_tree.case_id:
            raise ValueError(
                f"case_id 不匹配 / case_id mismatch: "
                f"setup_input={setup_input.case_id!r} vs "
                f"issue_tree={issue_tree.case_id!r}"
            )

    async def plan(
        self,
        setup_input: ProcedureSetupInput,
        issue_tree: IssueTree,
        run_id: str,
    ) -> ProcedureSetupResult:
        """执行程序设置规划。
        Execute procedure setup planning.

        Args:
            setup_input: 程序设置输入合约 / Procedure setup engine input contract
            issue_tree: 结构化争点树 / Structured issue tree
            run_id: 新建 Run 的 ID / Run ID for the newly created Run

        Returns:
            ProcedureSetupResult 包含完整程序状态序列、配置、时间线事件和 Run。
            LLM 调用或解析失败时返回 status="failed" 的结果，不抛出异常。
            ProcedureSetupResult with complete procedure states, config, timeline, and Run.
            On LLM failure or parse error, returns a failed ProcedureSetupResult.

        Raises:
            ValueError: 输入验证失败（issues 为空、case_id 不匹配）
                        Input validation failed (empty issues, case_id mismatch)
        """
        # 输入验证失败仍向上抛出 / Input validation errors still propagate
        self._validate_input(setup_input, issue_tree)

        case_id = setup_input.case_id
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            # 构建 prompt / Build prompt
            system_prompt = self._prompt_module.SYSTEM_PROMPT
            parties_block = self._prompt_module.format_parties_block(
                [p.model_dump() for p in setup_input.parties]
            )
            issue_tree_block = self._prompt_module.format_issue_tree_block(issue_tree.model_dump())
            user_prompt = self._prompt_module.SETUP_PROMPT.format(
                case_id=case_id,
                case_type=setup_input.case_type,
                parties_block=parties_block,
                issue_tree_block=issue_tree_block,
            )

            # 调用 LLM（结构化输出）/ Call LLM with structured output
            raw_dict = await self._call_llm_structured(system_prompt, user_prompt)
            llm_output = LLMProcedureOutput.model_validate(raw_dict)

            # 构建 ProcedureSetupResult / Build ProcedureSetupResult
            return self._build_result(
                llm_output=llm_output,
                setup_input=setup_input,
                issue_tree=issue_tree,
                case_id=case_id,
                run_id=run_id,
                now=now,
            )

        except Exception:
            # LLM 调用或解析失败：构造 failed 结果返回，不向上抛出
            # LLM call or parse failure: return a failed result instead of raising
            return self._build_failed_result(
                setup_input=setup_input,
                case_id=case_id,
                run_id=run_id,
                now=now,
            )

    async def _call_llm_structured(self, system: str, user: str) -> dict:
        """调用 LLM（结构化输出），失败时抛出异常由 plan() 捕获。
        Call LLM with structured output; exceptions are caught by plan().
        """
        return await call_structured_llm(
            self._llm_client,
            system=system,
            user=user,
            model=self._model,
            tool_name="setup_procedure",
            tool_description="根据案件类型、当事人和争点树生成结构化程序状态序列、配置和时间线事件。"
            "Generate structured procedure states, config, and timeline events "
            "from case type, parties, and issue tree.",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )

    def _build_result(
        self,
        llm_output: LLMProcedureOutput,
        setup_input: ProcedureSetupInput,
        issue_tree: IssueTree,
        case_id: str,
        run_id: str,
        now: str,
    ) -> ProcedureSetupResult:
        """将 LLM 输出规范化为 ProcedureSetupResult。
        Normalize LLM output into a ProcedureSetupResult.

        强制执行合约不变量 / Enforces contract invariants:
        - 按 PHASE_ORDER 重新排序并覆盖全部八个阶段（补充缺失阶段）
        - state_id 和 next_state_ids 由引擎确定性生成
        - judge_questions 强制移除 owner_private
        - output_branching 强制仅保留 admitted_for_discussion
        """
        # 从 LLM 输出建立 phase → LLMProcedureState 映射 / Map phase → LLMProcedureState
        llm_phase_map: dict[str, LLMProcedureState] = {}
        for ls in llm_output.procedure_states:
            if ls.phase in PHASE_ORDER:
                llm_phase_map[ls.phase] = ls

        # 按标准阶段顺序构建 ProcedureState 列表
        # Build ProcedureState list in canonical phase order
        procedure_states: list[ProcedureState] = []
        for idx, phase in enumerate(PHASE_ORDER):
            ls = llm_phase_map.get(phase)
            if ls is not None:
                # 使用 LLM 输出，强制执行访问控制约束
                # Use LLM output, enforcing access control constraints
                readable_domains = _sanitize_access_domains(ls.readable_access_domains, phase)
                ev_statuses = _sanitize_evidence_statuses(ls.admissible_evidence_statuses, phase)
                state = ProcedureState(
                    state_id=_make_state_id(case_id, phase),
                    case_id=case_id,
                    phase=phase,
                    round_index=idx,
                    allowed_role_codes=ls.allowed_role_codes,
                    readable_access_domains=readable_domains,
                    writable_object_types=ls.writable_object_types,
                    admissible_evidence_statuses=ev_statuses,
                    open_issue_ids=[],  # 在程序设置阶段全部初始化为空 / Empty at setup time
                    entry_conditions=ls.entry_conditions,
                    exit_conditions=ls.exit_conditions,
                    next_state_ids=_build_next_state_ids(case_id, phase),
                )
            else:
                # LLM 未输出该阶段，使用默认配置 / Use default config for missing phase
                default = _DEFAULT_PHASE_CONFIG.get(phase, {})
                state = ProcedureState(
                    state_id=_make_state_id(case_id, phase),
                    case_id=case_id,
                    phase=phase,
                    round_index=idx,
                    allowed_role_codes=default.get("allowed_role_codes", []),
                    readable_access_domains=_sanitize_access_domains(
                        default.get("readable_access_domains", []), phase
                    ),
                    writable_object_types=default.get("writable_object_types", []),
                    admissible_evidence_statuses=_sanitize_evidence_statuses(
                        default.get("admissible_evidence_statuses", []), phase
                    ),
                    open_issue_ids=[],
                    entry_conditions=default.get("entry_conditions", []),
                    exit_conditions=default.get("exit_conditions", []),
                    next_state_ids=_build_next_state_ids(case_id, phase),
                )
            procedure_states.append(state)

        # 构建 ProcedureConfig / Build ProcedureConfig
        llm_cfg = llm_output.procedure_config
        procedure_config = ProcedureConfig(
            case_type=setup_input.case_type,
            total_phases=len(PHASE_ORDER),
            evidence_submission_deadline_days=max(1, llm_cfg.evidence_submission_deadline_days),
            evidence_challenge_window_days=max(1, llm_cfg.evidence_challenge_window_days),
            max_rounds_per_phase=max(1, llm_cfg.max_rounds_per_phase),
            applicable_laws=llm_cfg.applicable_laws,
        )

        # 构建时间线事件 / Build timeline events
        timeline_events = self._build_timeline_events(llm_output.timeline_events, case_id)

        # 构建可追溯的输入快照 / Build traceable input snapshot
        input_snapshot = self._build_input_snapshot(issue_tree)

        # 输出引用回连 ProcedureState 产物 / Output refs back to ProcedureState artifacts
        output_refs = [
            ArtifactRef(
                index_name="artifact_index",
                object_type="AgentOutput",
                object_id=_make_state_id(case_id, PHASE_ORDER[0]),
                storage_ref=f"artifact_index/AgentOutput/{_make_state_id(case_id, PHASE_ORDER[0])}",
            )
        ]

        run = Run(
            run_id=run_id,
            case_id=case_id,
            workspace_id=setup_input.workspace_id,
            scenario_id=None,
            trigger_type="procedure_setup",
            input_snapshot=input_snapshot,
            output_refs=output_refs,
            started_at=now,
            finished_at=now,
            status="completed",
        )

        return ProcedureSetupResult(
            procedure_states=procedure_states,
            procedure_config=procedure_config,
            timeline_events=timeline_events,
            run=run,
        )

    def _build_timeline_events(
        self,
        llm_events: list,
        case_id: str,
    ) -> list[TimelineEvent]:
        """规范化时间线事件列表。
        Normalize timeline events list.

        - 过滤非法 phase 值
        - 若 LLM 无有效输出，补充默认时间线事件
        Filter invalid phase values; add fallback events if LLM returns nothing.
        """
        events: list[TimelineEvent] = []
        event_counter: dict[str, int] = {}

        for llm_ev in llm_events:
            phase = llm_ev.phase
            if phase not in PHASE_ORDER:
                continue
            if not llm_ev.event_type or not llm_ev.description:
                continue
            count = event_counter.get(phase, 0) + 1
            event_counter[phase] = count
            event_id = f"tevt-{case_id}-{phase}-{count:03d}"
            events.append(
                TimelineEvent(
                    event_id=event_id,
                    event_type=llm_ev.event_type,
                    phase=phase,
                    description=llm_ev.description,
                    relative_day=max(0, llm_ev.relative_day),
                    is_mandatory=llm_ev.is_mandatory,
                )
            )

        # 若无有效事件，补充默认时间线 / Add fallback if no valid events
        if not events:
            events = [
                TimelineEvent(
                    event_id=f"tevt-{case_id}-evidence_submission-001",
                    event_type="evidence_submission_deadline",
                    phase="evidence_submission",
                    description="举证期限届满 / Evidence submission deadline",
                    relative_day=15,
                    is_mandatory=True,
                ),
                TimelineEvent(
                    event_id=f"tevt-{case_id}-evidence_challenge-001",
                    event_type="evidence_challenge_deadline",
                    phase="evidence_challenge",
                    description="质证期限届满 / Evidence challenge deadline",
                    relative_day=25,
                    is_mandatory=True,
                ),
            ]

        return events

    def _build_input_snapshot(self, issue_tree: IssueTree) -> InputSnapshot:
        """构建可追溯的输入快照。
        Build a traceable input snapshot from the issue tree.
        """
        material_refs = [
            MaterialRef(
                index_name="material_index",
                object_type="Issue",
                object_id=issue.issue_id,
                storage_ref=f"material_index/Issue/{issue.issue_id}",
            )
            for issue in issue_tree.issues
        ] + [
            MaterialRef(
                index_name="material_index",
                object_type="Burden",
                object_id=burden.burden_id,
                storage_ref=f"material_index/Burden/{burden.burden_id}",
            )
            for burden in issue_tree.burdens
        ]
        return InputSnapshot(material_refs=material_refs, artifact_refs=[])

    def _build_failed_result(
        self,
        setup_input: ProcedureSetupInput,
        case_id: str,
        run_id: str,
        now: str,
    ) -> ProcedureSetupResult:
        """构建失败时的 ProcedureSetupResult（使用默认配置）。
        Build a failed ProcedureSetupResult using default phase config.

        失败时仍返回完整的程序状态序列，确保下游工作流不中断。
        Returns a complete procedure state sequence even on failure,
        ensuring downstream workflow continuity.
        """
        procedure_states = [
            ProcedureState(
                state_id=_make_state_id(case_id, phase),
                case_id=case_id,
                phase=phase,
                round_index=idx,
                **{
                    k: _sanitize_access_domains(v, phase)
                    if k == "readable_access_domains"
                    else _sanitize_evidence_statuses(v, phase)
                    if k == "admissible_evidence_statuses"
                    else v
                    for k, v in _DEFAULT_PHASE_CONFIG.get(phase, {}).items()
                },
                open_issue_ids=[],
                next_state_ids=_build_next_state_ids(case_id, phase),
            )
            for idx, phase in enumerate(PHASE_ORDER)
        ]

        procedure_config = ProcedureConfig(
            case_type=setup_input.case_type,
            total_phases=len(PHASE_ORDER),
            evidence_submission_deadline_days=15,
            evidence_challenge_window_days=10,
            max_rounds_per_phase=3,
            applicable_laws=[],
        )

        timeline_events = [
            TimelineEvent(
                event_id=f"tevt-{case_id}-evidence_submission-001",
                event_type="evidence_submission_deadline",
                phase="evidence_submission",
                description="举证期限届满（默认）/ Evidence submission deadline (default)",
                relative_day=15,
                is_mandatory=True,
            ),
        ]

        run = Run(
            run_id=run_id,
            case_id=case_id,
            workspace_id=setup_input.workspace_id,
            scenario_id=None,
            trigger_type="procedure_setup",
            input_snapshot=InputSnapshot(),
            output_refs=[],
            started_at=now,
            finished_at=now,
            status="failed",
        )

        return ProcedureSetupResult(
            procedure_states=procedure_states,
            procedure_config=procedure_config,
            timeline_events=timeline_events,
            run=run,
        )
