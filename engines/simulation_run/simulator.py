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

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

from engines.shared.json_utils import _extract_json_object  # noqa: F401 — re-exported for tests
from engines.shared.models import LLMClient
from engines.shared.structured_output import call_structured_llm

from .schemas import (
    ArtifactRef,
    ChangeItem,
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

# tool_use JSON Schema（模块加载时计算一次）
_TOOL_SCHEMA: dict = LLMDiffOutput.model_json_schema()


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
            raise ValueError("issue_tree.issues 不能为空 / issue_tree.issues cannot be empty")
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
            from .prompts import plugin

            system_prompt = self._prompt_module.SYSTEM_PROMPT
            user_prompt = plugin.get_prompt(
                "simulation_run",
                self._case_type,
                {
                    "case_id": case_id,
                    "scenario_id": scenario_input.scenario_id,
                    "issue_tree": issue_tree.model_dump(),
                    "evidence_list": [e.model_dump() for e in evidence_index.evidence],
                    "change_set": [c.model_dump() for c in scenario_input.change_set],
                },
            )

            # 调用 LLM（结构化输出）/ Call LLM with structured output
            raw_dict = await self._call_llm_structured(system_prompt, user_prompt)
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
                scenario_input.scenario_id,
                case_id,
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

    async def _call_llm_structured(self, system: str, user: str) -> dict:
        """调用 LLM（结构化输出），失败时抛出异常由 simulate() 捕获。"""
        return await call_structured_llm(
            self._llm_client,
            system=system,
            user=user,
            model=self._model,
            tool_name="simulate_scenario",
            tool_description="根据变更集推演场景对争点树的影响，生成结构化差异摘要。"
            "Simulate the impact of a change set on the issue tree, "
            "generating a structured diff summary.",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
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
            if c.target_object_type.value == "Evidence" and c.target_object_id in known_evidence_ids
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
            diff_entries.append(
                DiffEntry(
                    issue_id=llm_entry.issue_id,
                    impact_description=impact,
                    direction=_resolve_direction(llm_entry.direction),
                )
            )

        # 若 LLM 无有效输出，对所有争点补充保底条目
        # If LLM returns no valid entries, add fallback entries for all issues
        if not diff_entries:
            for issue in issue_tree.issues:
                diff_entries.append(
                    DiffEntry(
                        issue_id=issue.issue_id,
                        impact_description=(
                            f"变更集对争点「{issue.title}」的影响待分析。"
                            f"/ Impact of change_set on issue '{issue.title}' requires analysis."
                        ),
                        direction=DiffDirection.neutral,
                    )
                )

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


# ---------------------------------------------------------------------------
# What-if 分析入口 / What-if analysis entry points
# ---------------------------------------------------------------------------


def load_baseline(baseline_dir: str | Path) -> tuple[IssueTree, EvidenceIndex, str]:
    """从 baseline run 输出目录加载 IssueTree + EvidenceIndex。
    Load IssueTree + EvidenceIndex from a baseline run output directory.

    Args:
        baseline_dir: baseline run 的输出目录路径 / Path to baseline run output directory

    Returns:
        (issue_tree, evidence_index, run_id) 三元组

    Raises:
        FileNotFoundError: 目录不存在或缺少必要文件
    """
    base = Path(baseline_dir)
    if not base.is_dir():
        raise FileNotFoundError(f"Baseline 目录不存在 / Baseline directory not found: {base}")

    it_path = base / "issue_tree.json"
    if not it_path.exists():
        raise FileNotFoundError(f"缺少 issue_tree.json / Missing issue_tree.json in {base}")

    ei_path = base / "evidence_index.json"
    if not ei_path.exists():
        raise FileNotFoundError(f"缺少 evidence_index.json / Missing evidence_index.json in {base}")

    issue_tree = IssueTree.model_validate_json(it_path.read_text(encoding="utf-8"))
    evidence_index = EvidenceIndex.model_validate_json(ei_path.read_text(encoding="utf-8"))

    # 从 result.json 获取 run_id（如果存在），否则用目录名
    # Get run_id from result.json if available, otherwise use directory name
    result_path = base / "result.json"
    if result_path.exists():
        result_data = json.loads(result_path.read_text(encoding="utf-8"))
        run_id = result_data.get("run_id", base.name)
    else:
        run_id = base.name

    return issue_tree, evidence_index, run_id


def parse_change_set(change_set_path: str | Path) -> tuple[str, list[ChangeItem]]:
    """解析 change_set YAML 文件。
    Parse a change_set YAML file.

    Expected YAML format::

        scenario_id: "scenario-whatif-001"
        changes:
          - target_object_type: Evidence
            target_object_id: "EV-03"
            field_path: "summary"
            old_value: "original text"
            new_value: "modified text"

    Args:
        change_set_path: YAML 文件路径 / Path to YAML file

    Returns:
        (scenario_id, change_items) 二元组

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: YAML 格式不正确或缺少必要字段
    """
    cs_path = Path(change_set_path)
    if not cs_path.exists():
        raise FileNotFoundError(f"change_set 文件不存在 / change_set file not found: {cs_path}")

    data = yaml.safe_load(cs_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("change_set YAML 必须是字典 / change_set YAML must be a mapping")

    scenario_id = data.get("scenario_id")
    if not scenario_id:
        raise ValueError(
            "change_set YAML 缺少 scenario_id / Missing scenario_id in change_set YAML"
        )

    changes_raw = data.get("changes")
    if not isinstance(changes_raw, list) or len(changes_raw) == 0:
        raise ValueError(
            "change_set YAML 的 changes 不能为空 / "
            "changes must be a non-empty list in change_set YAML"
        )

    change_items: list[ChangeItem] = []
    for i, entry in enumerate(changes_raw):
        try:
            change_items.append(ChangeItem.model_validate(entry))
        except Exception as exc:
            raise ValueError(
                f"changes[{i}] 格式无效 / Invalid change entry at index {i}: {exc}"
            ) from exc

    return scenario_id, change_items


async def run_whatif(
    baseline_dir: str | Path,
    change_set_path: str | Path,
    llm_client: LLMClient,
    *,
    case_type: str = "civil_loan",
    model: str = "claude-sonnet-4-20250514",
    workspace_id: str = "workspace-default",
) -> ScenarioResult:
    """执行 what-if 分析的高层入口。
    High-level entry point for what-if analysis.

    从 baseline 输出目录加载 IssueTree + EvidenceIndex，解析 change_set YAML，
    调用 ScenarioSimulator.simulate()，并将结果保存到输出目录。

    Args:
        baseline_dir: baseline run 的输出目录
        change_set_path: change_set YAML 文件路径
        llm_client: LLM 客户端
        case_type: 案由类型
        model: LLM 模型名称
        workspace_id: 工作空间 ID

    Returns:
        ScenarioResult 包含推演结果

    Raises:
        FileNotFoundError: baseline 目录或 change_set 文件不存在
        ValueError: 输入数据无效
    """
    # 1. 加载 baseline / Load baseline
    issue_tree, evidence_index, baseline_run_id = load_baseline(baseline_dir)

    # 2. 解析 change_set / Parse change_set
    scenario_id, change_items = parse_change_set(change_set_path)

    # 3. 构建 ScenarioInput / Build ScenarioInput
    scenario_input = ScenarioInput(
        scenario_id=scenario_id,
        baseline_run_id=baseline_run_id,
        change_set=change_items,
        workspace_id=workspace_id,
    )

    # 4. 执行推演 / Execute simulation
    run_id = f"run-scenario-{uuid.uuid4().hex[:12]}"
    simulator = ScenarioSimulator(
        llm_client=llm_client,
        case_type=case_type,
        model=model,
    )
    result = await simulator.simulate(
        scenario_input=scenario_input,
        issue_tree=issue_tree,
        evidence_index=evidence_index,
        run_id=run_id,
    )

    # 5. 保存结果 / Save result
    base = Path(baseline_dir)
    out_dir = base / f"scenario_{scenario_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    diff_path = out_dir / "diff_summary.json"
    diff_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    logger.info("What-if 结果已保存 / What-if result saved: %s", diff_path)

    return result
