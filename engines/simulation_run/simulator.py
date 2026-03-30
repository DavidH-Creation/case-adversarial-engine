"""
场景推演引擎核心模块
Scenario simulator core module.

将争点树（IssueTree）和证据索引（EvidenceIndex）结合场景变更集（ChangeSet），
通过 LLM 生成结构化差异摘要（DiffSummary）。
Generates a structured diff summary from IssueTree + EvidenceIndex + ChangeSet via LLM.

合约保证 / Contract guarantees:
- 每条 diff_entry 有 impact_description（不为空）
- 每条 diff_entry.direction 为合法枚举值
- affected_issue_ids 覆盖所有 diff_entry.issue_id
- baseline 场景不执行（change_set = [] 时拒绝调用）
- baseline Run 不被修改，始终创建新 Run
- trigger_type 固定为 "scenario_execution"
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

from engines.shared.json_utils import _extract_json_object

from .schemas import (
    ArtifactRef,
    DiffDirection,
    DiffEntry,
    EvidenceIndex,
    InputSnapshot,
    IssueTree,
    LLMDiffOutput,
    MaterialRef,
    Run,
    Scenario,
    ScenarioInput,
    ScenarioResult,
    ScenarioStatus,
)

# Re-export for test compatibility
# _extract_json_object is imported above from engines.shared.json_utils


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
# direction 解析工具 / direction resolution utility
# ---------------------------------------------------------------------------


def _resolve_direction(raw: str) -> DiffDirection:
    """将 LLM 返回的 direction 字符串解析为枚举值。
    Resolve raw direction string to DiffDirection enum.
    Defaults to 'neutral' for unknown values.
    """
    _MAP = {
        "strengthen": DiffDirection.strengthen,
        "增强": DiffDirection.strengthen,
        "weaken": DiffDirection.weaken,
        "削弱": DiffDirection.weaken,
        "neutral": DiffDirection.neutral,
        "中性": DiffDirection.neutral,
        "无": DiffDirection.neutral,
    }
    return _MAP.get(raw.strip().lower(), DiffDirection.neutral)


# ---------------------------------------------------------------------------
# 主引擎类 / Main engine class
# ---------------------------------------------------------------------------


class ScenarioSimulator:
    """场景推演器
    Scenario Simulator.

    输入 IssueTree + EvidenceIndex + ScenarioInput，输出 ScenarioResult。
    Takes IssueTree + EvidenceIndex + ScenarioInput, outputs a ScenarioResult.

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
        scenario_input: ScenarioInput,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
    ) -> None:
        """验证输入数据合法性。
        Validate input data validity.

        Raises:
            ValueError: issues 为空、case_id 不匹配，或 change_set 为空（baseline 不执行）。
                        Empty issues, case_id mismatch, or empty change_set (baseline not executed).
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
        # baseline anchor 合约：change_set 为空时不执行
        # Baseline anchor contract: refuse execution when change_set is empty
        if not scenario_input.change_set:
            raise ValueError(
                "change_set 为空——这是 baseline anchor 场景，不应调用 simulate() 执行推演。"
                " / change_set is empty — this is a baseline anchor scenario; "
                "do not call simulate() for baseline anchors."
            )

    async def simulate(
        self,
        scenario_input: ScenarioInput,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        run_id: str,
    ) -> ScenarioResult:
        """执行场景推演。
        Execute scenario simulation.

        Args:
            scenario_input: 场景输入合约 / Scenario engine input contract
            issue_tree: 结构化争点树 / Structured issue tree
            evidence_index: 证据索引 / Evidence index
            run_id: 新建 Run 的 ID / Run ID for the newly created Run

        Returns:
            ScenarioResult 包含更新后的 Scenario 和新建 Run。
            LLM 调用或解析失败时返回 status="failed" 的 ScenarioResult，不抛出异常。
            ScenarioResult with updated Scenario and newly created Run.
            On LLM failure or parse error, returns a ScenarioResult with status="failed".

        Raises:
            ValueError: 输入验证失败（change_set 为空、case_id 不匹配、issues 为空）
                        Input validation failed (empty change_set, case_id mismatch, empty issues)
        """
        # 输入验证失败仍向上抛出 / Input validation errors still propagate
        self._validate_input(scenario_input, issue_tree, evidence_index)

        case_id = issue_tree.case_id
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            # 构建 prompt / Build prompt
            system_prompt = self._prompt_module.SYSTEM_PROMPT
            issue_tree_block = self._prompt_module.format_issue_tree_block(
                issue_tree.model_dump()
            )
            evidence_block = self._prompt_module.format_evidence_block(
                [e.model_dump() for e in evidence_index.evidence]
            )
            change_set_block = self._prompt_module.format_change_set_block(
                [c.model_dump() for c in scenario_input.change_set]
            )
            user_prompt = self._prompt_module.SIMULATION_PROMPT.format(
                case_id=case_id,
                scenario_id=scenario_input.scenario_id,
                issue_tree_block=issue_tree_block,
                evidence_block=evidence_block,
                change_set_block=change_set_block,
            )

            # 调用 LLM（带重试）/ Call LLM with retry
            raw_response = await self._call_llm_with_retry(system_prompt, user_prompt)

            # 解析 LLM 输出 / Parse LLM output
            raw_dict = _extract_json_object(raw_response)
            llm_output = LLMDiffOutput.model_validate(raw_dict)

            # 构建 ScenarioResult / Build ScenarioResult
            return self._build_result(
                llm_output=llm_output,
                scenario_input=scenario_input,
                issue_tree=issue_tree,
                evidence_index=evidence_index,
                case_id=case_id,
                run_id=run_id,
                now=now,
            )

        except Exception:
            # LLM 调用或解析失败：构造 failed ScenarioResult 返回，不向上抛出
            # LLM call or parse failure: return a failed ScenarioResult instead of raising
            logger.exception(
                "场景推演失败，返回 failed ScenarioResult / "
                "Scenario simulation failed, returning failed ScenarioResult: "
                "scenario_id=%s, case_id=%s",
                scenario_input.scenario_id, case_id,
            )
            failed_scenario = Scenario(
                scenario_id=scenario_input.scenario_id,
                case_id=case_id,
                baseline_run_id=scenario_input.baseline_run_id,
                change_set=scenario_input.change_set,
                diff_summary=[],
                affected_issue_ids=[],
                affected_evidence_ids=[],
                status=ScenarioStatus.failed,
            )
            failed_run = Run(
                run_id=run_id,
                case_id=case_id,
                workspace_id=scenario_input.workspace_id,
                scenario_id=scenario_input.scenario_id,
                trigger_type="scenario_execution",
                input_snapshot=InputSnapshot(),
                output_refs=[],
                started_at=now,
                finished_at=now,
                status="failed",
            )
            return ScenarioResult(scenario=failed_scenario, run=failed_run)

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

    def _build_result(
        self,
        llm_output: LLMDiffOutput,
        scenario_input: ScenarioInput,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        case_id: str,
        run_id: str,
        now: str,
    ) -> ScenarioResult:
        """将 LLM 输出规范化为 ScenarioResult。
        Normalize LLM output into a ScenarioResult.

        强制执行合约不变量 / Enforces contract invariants:
        - 过滤非法 issue_id（仅保留争点树中已知 ID）
        - 过滤非法 evidence_id（仅保留证据索引中已知 ID）
        - LLM 无输出时补充保底条目
        - 补全 affected_issue_ids 和 affected_evidence_ids
        """
        known_issue_ids: set[str] = {i.issue_id for i in issue_tree.issues}
        known_evidence_ids: set[str] = {e.evidence_id for e in evidence_index.evidence}

        # 收集 change_set 涉及的 evidence_id / Collect evidence IDs referenced in change_set
        change_set_evidence_ids: list[str] = [
            c.target_object_id
            for c in scenario_input.change_set
            if c.target_object_type.value == "Evidence"
            and c.target_object_id in known_evidence_ids
        ]

        # 规范化 diff_entries / Normalize diff entries
        diff_entries: list[DiffEntry] = []
        for llm_entry in llm_output.diff_entries:
            # 过滤非法争点 ID / Filter entries with unknown issue_ids
            if llm_entry.issue_id not in known_issue_ids:
                continue
            impact = llm_entry.impact_description.strip() or (
                f"变更影响了争点 {llm_entry.issue_id} / Change affected issue {llm_entry.issue_id}"
            )
            diff_entries.append(DiffEntry(
                issue_id=llm_entry.issue_id,
                impact_description=impact,
                direction=_resolve_direction(llm_entry.direction),
            ))

        # 若 LLM 无有效输出，对所有争点补充保底条目
        # If LLM returns no valid entries, add fallback entries for all issues
        if not diff_entries:
            for issue in issue_tree.issues:
                diff_entries.append(DiffEntry(
                    issue_id=issue.issue_id,
                    impact_description=(
                        f"变更集对争点「{issue.title}」的影响待分析。"
                        f"/ Impact of change_set on issue '{issue.title}' requires analysis."
                    ),
                    direction=DiffDirection.neutral,
                ))

        # 计算 affected_issue_ids（去重）/ Compute affected_issue_ids (deduplicated)
        affected_issue_ids: list[str] = list(dict.fromkeys(e.issue_id for e in diff_entries))

        # 计算 affected_evidence_ids（去重）/ Compute affected_evidence_ids (deduplicated)
        affected_evidence_ids: list[str] = list(dict.fromkeys(change_set_evidence_ids))

        # 构建可追溯的输入快照 / Build traceable input snapshot
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
                object_type="Evidence",
                object_id=ev.evidence_id,
                storage_ref=f"material_index/Evidence/{ev.evidence_id}",
            )
            for ev in evidence_index.evidence
        ]

        input_snapshot = InputSnapshot(
            material_refs=material_refs,
            artifact_refs=[],
        )

        # 输出引用回连 Scenario 产物 / Output ref back to the Scenario artifact
        output_refs = [
            ArtifactRef(
                index_name="artifact_index",
                object_type="Scenario",
                object_id=scenario_input.scenario_id,
                storage_ref=f"artifact_index/Scenario/{scenario_input.scenario_id}",
            )
        ]

        # 构建新 Run（trigger_type 固定为 scenario_execution）
        # Build new Run (trigger_type fixed to "scenario_execution")
        run = Run(
            run_id=run_id,
            case_id=case_id,
            workspace_id=scenario_input.workspace_id,
            scenario_id=scenario_input.scenario_id,
            trigger_type="scenario_execution",
            input_snapshot=input_snapshot,
            output_refs=output_refs,
            started_at=now,
            finished_at=now,
            status="completed",
        )

        # 构建更新后的 Scenario / Build updated Scenario
        scenario = Scenario(
            scenario_id=scenario_input.scenario_id,
            case_id=case_id,
            baseline_run_id=scenario_input.baseline_run_id,
            change_set=scenario_input.change_set,
            diff_summary=diff_entries,
            affected_issue_ids=affected_issue_ids,
            affected_evidence_ids=affected_evidence_ids,
            status=ScenarioStatus.completed,
        )

        return ScenarioResult(scenario=scenario, run=run)
