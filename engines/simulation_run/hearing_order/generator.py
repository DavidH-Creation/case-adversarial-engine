"""
HearingOrderGenerator — 庭审顺序建议生成器（P2）。
Court Hearing Order Generator (P2).

职责 / Responsibilities:
1. 接收争点依赖图 + 当事方立场
2. 基于拓扑排序确定争点分析顺序（依赖方先审）
3. 按争点类型分组庭审阶段（程序性 → 事实性 → 法律性 → 损害赔偿）
4. 基于 outcome_impact 估算每个争点的庭审时长
5. 输出 HearingOrderResult（纯规则层，不调用 LLM）

合约保证 / Contract guarantees:
- 所有输入争点均出现在 issue_presentation_order 中（无遗漏）
- 依赖图拓扑排序中的环路节点附加到对应阶段末尾
- total_estimated_duration_minutes == sum(phase.estimated_duration_minutes)
- 不调用 LLM（纯规则层）
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from engines.shared.models import Issue, IssueType, OutcomeImpact

from .schemas import (
    HearingOrderInput,
    HearingOrderResult,
    HearingPhase,
    IssueTimeEstimate,
)

logger = logging.getLogger(__name__)

# 庭审时长估算（分钟）：按 outcome_impact 分级
_DURATION_BY_IMPACT: dict[OutcomeImpact, int] = {
    OutcomeImpact.high: 30,
    OutcomeImpact.medium: 20,
    OutcomeImpact.low: 10,
}
_DEFAULT_DURATION = 15  # outcome_impact 未评估时的默认时长

# 阶段划分优先级（数值越小越先）
_PHASE_ORDER: dict[str, int] = {
    "procedural": 0,
    "factual": 1,
    "legal": 2,
    "damages": 3,
}


class HearingOrderGenerator:
    """庭审顺序建议生成器。

    纯规则层，不持有外部状态，可安全复用同一实例。

    使用方式 / Usage:
        generator = HearingOrderGenerator()
        result = generator.generate(inp)
    """

    def generate(self, inp: HearingOrderInput) -> HearingOrderResult:
        """生成庭审顺序建议。

        Args:
            inp: 包含依赖图、争点列表和当事方立场的输入

        Returns:
            HearingOrderResult — 含庭审阶段、顺序和时间估算
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        order_id = str(uuid.uuid4())
        issues = list(inp.issues)

        if not issues:
            return HearingOrderResult(
                order_id=order_id,
                case_id=inp.case_id,
                phases=[],
                issue_presentation_order=[],
                issue_time_estimates=[],
                total_estimated_duration_minutes=0,
                ordering_rationale="无争点输入",
                metadata={"issue_count": 0},
                created_at=now,
            )

        issue_map: dict[str, Issue] = {i.issue_id: i for i in issues}
        graph = inp.dependency_graph

        # 1. 从拓扑排序获取基础顺序
        topo_order = list(graph.topological_order)
        cycle_ids = {
            issue_id for cycle in graph.cycles for issue_id in cycle
        }
        # 将环路节点追加到顺序末尾（按 issue_id 字典序保持稳定）
        cycle_nodes_ordered = [
            iid for iid in sorted(cycle_ids)
            if iid in issue_map
        ]

        # 只保留本次 issues 中存在的 issue_id
        ordered_ids = [iid for iid in topo_order if iid in issue_map]
        # 补全 topo 中未出现的 issue（依赖图未包含的争点）
        topo_set = set(ordered_ids) | set(cycle_nodes_ordered)
        orphan_ids = [
            i.issue_id for i in issues
            if i.issue_id not in topo_set
        ]

        full_order = ordered_ids + cycle_nodes_ordered + orphan_ids

        # 2. 当事方偏好调整（将 priority_issue_ids 提前至各自阶段首位）
        plaintiff_priority = set()
        for pos in inp.party_positions:
            if pos.role == "plaintiff":
                plaintiff_priority.update(pos.priority_issue_ids)

        # 3. 按争点类型分组
        phases_map: dict[str, list[str]] = {
            "procedural": [],
            "factual": [],
            "legal": [],
            "damages": [],
        }

        for issue_id in full_order:
            issue = issue_map.get(issue_id)
            if issue is None:
                continue
            phase_key = self._classify_phase(issue)
            phases_map[phase_key].append(issue_id)

        # 4. 原告方优先争点排到对应阶段首位
        for phase_key, phase_issue_ids in phases_map.items():
            priority_in_phase = [
                iid for iid in phase_issue_ids if iid in plaintiff_priority
            ]
            rest_in_phase = [
                iid for iid in phase_issue_ids if iid not in plaintiff_priority
            ]
            phases_map[phase_key] = priority_in_phase + rest_in_phase

        # 5. 构建 issue_presentation_order（按阶段顺序拼接）
        phase_names = {
            "procedural": "程序性事项",
            "factual": "事实争点",
            "legal": "法律争点",
            "damages": "损害赔偿争点",
        }
        phase_rationales = {
            "procedural": "程序性争点优先处理，为实体审理奠定基础",
            "factual": "事实争点按依赖关系顺序审理（被依赖方先审）",
            "legal": "法律适用争点在事实认定后处理",
            "damages": "损害赔偿金额计算在责任认定后处理",
        }

        phases: list[HearingPhase] = []
        issue_presentation_order: list[str] = []
        issue_time_estimates: list[IssueTimeEstimate] = []

        for phase_key in ["procedural", "factual", "legal", "damages"]:
            phase_issue_ids = phases_map[phase_key]
            if not phase_issue_ids:
                continue

            phase_duration = 0
            for issue_id in phase_issue_ids:
                issue = issue_map.get(issue_id)
                duration = self._estimate_duration(issue)
                phase_duration += duration
                issue_time_estimates.append(
                    IssueTimeEstimate(
                        issue_id=issue_id,
                        estimated_minutes=duration,
                        rationale=self._duration_rationale(issue),
                    )
                )

            issue_presentation_order.extend(phase_issue_ids)
            phases.append(
                HearingPhase(
                    phase_id=f"phase-{len(phases) + 1}",
                    phase_name=phase_names[phase_key],
                    issue_ids=phase_issue_ids,
                    estimated_duration_minutes=phase_duration,
                    phase_rationale=phase_rationales[phase_key],
                )
            )

        total_duration = sum(p.estimated_duration_minutes for p in phases)

        rationale_parts = [
            "庭审顺序依据：",
            f"1. 拓扑排序（{len(ordered_ids)} 个争点按依赖关系排序）",
        ]
        if cycle_nodes_ordered:
            rationale_parts.append(
                f"2. 环路争点（{len(cycle_nodes_ordered)} 个）附加到对应阶段末尾"
            )
        if orphan_ids:
            rationale_parts.append(
                f"3. 孤立争点（{len(orphan_ids)} 个，依赖图未包含）按 issue_id 顺序排列"
            )
        if plaintiff_priority:
            rationale_parts.append(
                f"4. 原告方优先争点（{len(plaintiff_priority)} 个）提前至各阶段首位"
            )

        return HearingOrderResult(
            order_id=order_id,
            case_id=inp.case_id,
            phases=phases,
            issue_presentation_order=issue_presentation_order,
            issue_time_estimates=issue_time_estimates,
            total_estimated_duration_minutes=total_duration,
            ordering_rationale=" ".join(rationale_parts),
            metadata={
                "issue_count": len(issues),
                "phase_count": len(phases),
                "has_cycles": graph.has_cycles,
                "cycle_node_count": len(cycle_nodes_ordered),
                "created_at": now,
            },
            created_at=now,
        )

    # ------------------------------------------------------------------
    # 辅助方法 / Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_phase(issue: Issue) -> str:
        """将争点分配到庭审阶段。

        规则（优先级降序）：
        1. procedural 类型 → "procedural"
        2. legal 类型 → "legal"
        3. 含 "利息" / "金额" / "计算" 等关键词的 factual → "damages"
        4. 其他 → "factual"
        """
        if issue.issue_type == IssueType.procedural:
            return "procedural"
        if issue.issue_type == IssueType.legal:
            return "legal"
        # 简单关键词检测判断损害赔偿争点
        damages_keywords = ("利息", "金额", "计算", "赔偿", "违约金", "罚息", "费用")
        if any(kw in issue.title for kw in damages_keywords):
            return "damages"
        return "factual"

    @staticmethod
    def _estimate_duration(issue: Issue | None) -> int:
        """估算单个争点的庭审时长（分钟）。"""
        if issue is None:
            return _DEFAULT_DURATION
        impact = getattr(issue, "outcome_impact", None)
        return _DURATION_BY_IMPACT.get(impact, _DEFAULT_DURATION)

    @staticmethod
    def _duration_rationale(issue: Issue | None) -> str:
        """生成时长估算依据说明。"""
        if issue is None:
            return "未知争点，使用默认时长"
        impact = getattr(issue, "outcome_impact", None)
        if impact is None:
            return "outcome_impact 未评估，使用默认时长 15 分钟"
        duration = _DURATION_BY_IMPACT[impact]
        return f"outcome_impact={impact.value}，预估 {duration} 分钟"
