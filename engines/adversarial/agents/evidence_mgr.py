"""
EvidenceManagerAgent — 整理双方证据清单，标记冲突。
EvidenceManagerAgent — organizes evidence lists and flags conflicts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from engines.shared.json_utils import _extract_json_object
from engines.shared.models import (
    AgentOutput,
    AgentRole,
    Evidence,
    EvidenceIndex,
    IssueTree,
    LLMClient,
    ProcedurePhase,
    StatementClass,
)

from ..schemas import ConflictEntry, RoundConfig
from .base_agent import AgentOutputValidationError


class EvidenceManagerAgent:
    """证据管理代理 — 整理双方证据，标记冲突项。
    Evidence manager agent — organizes party evidence and flags conflicts.

    不继承 BasePartyAgent（独立逻辑）。
    Does not inherit BasePartyAgent (standalone logic).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: RoundConfig,
    ) -> None:
        self._llm = llm_client
        self._config = config

    async def analyze(
        self,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        plaintiff_outputs: list[AgentOutput],
        defendant_outputs: list[AgentOutput],
        run_id: str,
        state_id: str,
        round_index: int,
    ) -> tuple[AgentOutput, list[ConflictEntry]]:
        """执行证据分析，返回 (AgentOutput, 冲突列表)。
        Execute evidence analysis, return (AgentOutput, conflict list).

        重试条件 / Retry on:
        - LLM 网络/API 错误
        - AgentOutputValidationError（空 issue_ids / evidence_citations）
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_analysis_prompt(
            issue_tree, evidence_index, plaintiff_outputs, defendant_outputs
        )
        last_error: str | None = None

        for attempt in range(1, self._config.max_retries + 1):
            current_prompt = user_prompt
            if last_error:
                current_prompt = (
                    f"{user_prompt}\n\n"
                    f"[上次输出验证失败，请修正：{last_error}]"
                )

            try:
                raw = await self._llm.create_message(
                    system=system_prompt,
                    user=current_prompt,
                    model=self._config.model,
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens_per_output,
                )
            except Exception as e:
                last_error = str(e)
                continue

            try:
                data = _extract_json_object(raw)
                output = self._build_agent_output(
                    data, run_id, state_id, round_index, evidence_index.case_id
                )
                conflicts = self._parse_conflicts(data)
                return output, conflicts
            except AgentOutputValidationError as e:
                last_error = str(e)
                continue

        raise RuntimeError(
            f"EvidenceManager LLM 调用失败，已重试 {self._config.max_retries} 次。"
            f"最后错误: {last_error}"
        )

    # ------------------------------------------------------------------
    # 内部方法 / Internal methods
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        return (
            "你是一位法庭证据管理员，职责是客观整理原被告双方的证据清单，\n"
            "识别双方证据之间的冲突（如同一事实，双方证据相互矛盾）。\n"
            "你不代表任何一方，保持中立。\n"
            "输出必须严格遵循JSON格式，不得输出JSON以外的内容。"
        )

    def _build_analysis_prompt(
        self,
        issue_tree: IssueTree,
        evidence_index: EvidenceIndex,
        plaintiff_outputs: list[AgentOutput],
        defendant_outputs: list[AgentOutput],
    ) -> str:
        # 证据清单按 owner 分组
        plaintiff_ev = [e for e in evidence_index.evidence if e.access_domain.value != "owner_private"
                        or e.owner_party_id in {o.owner_party_id for o in plaintiff_outputs}]
        defendant_ev = [e for e in evidence_index.evidence if e.access_domain.value != "owner_private"
                        or e.owner_party_id in {o.owner_party_id for o in defendant_outputs}]

        def fmt_ev(evs: list[Evidence]) -> str:
            if not evs:
                return "  （无）"
            return "\n".join(f"  [{e.evidence_id}] {e.title}: {e.summary}" for e in evs)

        def fmt_outputs(outs: list[AgentOutput]) -> str:
            if not outs:
                return "  （无）"
            return "\n".join(
                f"  [{o.output_id}] {o.title}\n    引用证据: {o.evidence_citations}"
                for o in outs
            )

        issues_text = "\n".join(
            f"  [{i.issue_id}] {i.title}" for i in issue_tree.issues
        )

        return f"""## 任务：整理证据清单并标记冲突

### 案件争点
{issues_text}

### 原告方提交的证据（含已引用）
{fmt_ev(plaintiff_ev)}

### 被告方提交的证据（含已引用）
{fmt_ev(defendant_ev)}

### 原告方已有论点摘要
{fmt_outputs(plaintiff_outputs)}

### 被告方已有论点摘要
{fmt_outputs(defendant_outputs)}

### 要求
1. 识别双方在同一争点上的证据冲突（不一致、相互矛盾、互相抵消）
2. 指出缺失证据（某争点上某方完全没有证据支撑）
3. 输出结构化冲突清单

### 输出格式（严格JSON）
{{
  "title": "证据整理摘要",
  "body": "（整体分析文字，不超过400字）",
  "issue_ids": ["受影响的争点ID列表"],
  "evidence_citations": ["分析中引用的证据ID列表，必须非空"],
  "risk_flags": ["风险标记"],
  "conflicts": [
    {{
      "issue_id": "争点ID",
      "plaintiff_evidence_ids": ["原告相关证据ID"],
      "defendant_evidence_ids": ["被告相关证据ID"],
      "conflict_description": "冲突描述"
    }}
  ]
}}"""

    def _parse_conflicts(self, data: dict[str, Any]) -> list[ConflictEntry]:
        conflicts = []
        for c in data.get("conflicts", []):
            if not c.get("issue_id") or not c.get("conflict_description"):
                continue
            conflicts.append(ConflictEntry(
                issue_id=c["issue_id"],
                plaintiff_evidence_ids=c.get("plaintiff_evidence_ids", []),
                defendant_evidence_ids=c.get("defendant_evidence_ids", []),
                conflict_description=c["conflict_description"],
            ))
        return conflicts

    def _build_agent_output(
        self,
        data: dict[str, Any],
        run_id: str,
        state_id: str,
        round_index: int,
        case_id: str,
    ) -> AgentOutput:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        output_id = f"output-evidence_manager-r{round_index}-{uuid.uuid4().hex[:8]}"

        issue_ids = data.get("issue_ids", [])
        evidence_citations = data.get("evidence_citations", [])

        if not issue_ids:
            raise AgentOutputValidationError(
                "EvidenceManager 输出缺少 issue_ids，请在 issue_ids 字段中提供至少一个争点 ID。"
            )
        if not evidence_citations:
            raise AgentOutputValidationError(
                "EvidenceManager 输出缺少 evidence_citations，请在 evidence_citations 字段中"
                "提供至少一个证据 ID。"
            )

        return AgentOutput(
            output_id=output_id,
            case_id=case_id,
            run_id=run_id,
            state_id=state_id,
            phase=ProcedurePhase.evidence_submission,
            round_index=round_index,
            agent_role_code=AgentRole.evidence_manager.value,
            owner_party_id="system",
            issue_ids=issue_ids,
            title=data.get("title", f"证据整理 第{round_index}轮"),
            body=data.get("body", ""),
            evidence_citations=evidence_citations,
            statement_class=StatementClass.fact,
            risk_flags=data.get("risk_flags", []),
            created_at=now,
        )

