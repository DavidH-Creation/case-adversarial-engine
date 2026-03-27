"""
案件工作区管理器 — 统一持久化入口。
WorkspaceManager — single persistence entry point for CaseWorkspace.

每个 save_* 和 save_run 调用都独立原子（write .tmp then replace）。
四步序列（创建 Run → 引擎执行 → 写产物 → 写 Run）由调用方（pipeline）负责编排；
WorkspaceManager 只保证每个单步的写操作原子性，不提供跨步事务。

Each save_* and save_run call is individually atomic (write .tmp then replace).
The four-step sequence (create Run → execute engines → save artifacts → save Run)
is orchestrated by the caller (pipeline); WorkspaceManager only guarantees
per-call atomicity, not cross-step transactions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from engines.shared.models import (
    AccessDomain,
    AgentOutput,
    Claim,
    Defense,
    EvidenceIndex,
    ExecutiveSummaryArtifact,
    InteractionTurn,
    IssueTree,
    ReportArtifact,
    Run,
    Scenario,
    WorkflowStage,
)


class WorkspaceManager:
    """案件工作区读写管理器。
    CaseWorkspace read/write manager.

    目录结构 / Directory layout:
        {base_dir}/{case_id}/
          workspace.json              # thin index
          runs/
            run_{run_id}.json         # Run snapshots
          artifacts/
            evidence_index.json
            claim_defense.json
            issue_tree.json
            report.json
            turns/
              turn_001.json           # InteractionTurn outputs
              turn_002.json
            scenarios/
              scenario_{id}.json      # Scenario outputs
    """

    def __init__(self, base_dir: Path, case_id: str) -> None:
        self.base_dir = base_dir
        self.case_id = case_id
        self.workspace_dir = base_dir / case_id

    # ------------------------------------------------------------------
    # 内部辅助 / Internal helpers
    # ------------------------------------------------------------------

    def _workspace_path(self) -> Path:
        return self.workspace_dir / "workspace.json"

    def _run_path(self, run_id: str) -> Path:
        return self.workspace_dir / "runs" / f"run_{run_id}.json"

    def _artifacts_dir(self) -> Path:
        return self.workspace_dir / "artifacts"

    def _atomic_write(self, path: Path, data: dict) -> None:
        """原子写操作：先写 .tmp 文件，再重命名替换目标。
        Atomic write: write to .tmp file then rename to target.
        On POSIX this is atomic; on Windows it is best-effort (os.replace).
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, path)  # atomic on POSIX; best-effort on Windows

    def _empty_workspace(self, case_type: str) -> dict:
        """构造初始 workspace.json 内容（run_ids 为空）。
        Build initial workspace.json content (empty run_ids).
        """
        return {
            "workspace_id": f"ws-{self.case_id}",
            "case_id": self.case_id,
            "case_type": case_type,
            "current_workflow_stage": WorkflowStage.case_structuring.value,
            "material_index": {
                "Party": [],
                "Claim": [],
                "Defense": [],
                "Issue": [],
                "Evidence": [],
                "Burden": [],
                "ProcedureState": [],
            },
            "artifact_index": {
                "AgentOutput": [],
                "ReportArtifact": [],
                "InteractionTurn": [],
                "Scenario": [],
                "ExecutiveSummaryArtifact": [],
            },
            "run_ids": [],
            "active_scenario_id": None,
            "status": "active",
        }

    def _load_or_raise(self) -> dict:
        """读取 workspace.json；若不存在则抛 ValueError。
        Load workspace.json; raise ValueError if not initialized.
        """
        ws = self.load_workspace()
        if ws is None:
            raise ValueError(
                f"Workspace not initialized for case_id={self.case_id!r}. "
                "Call init_workspace() first."
            )
        return ws

    # ------------------------------------------------------------------
    # 生命周期 / Lifecycle
    # ------------------------------------------------------------------

    def init_workspace(self, case_type: str) -> dict:
        """初始化工作区：创建目录结构和初始 workspace.json。
        Initialize workspace: create directory layout and initial workspace.json.
        Always overwrites any existing workspace.json.
        Returns the written workspace dict.
        """
        workspace = self._empty_workspace(case_type)
        self._atomic_write(self._workspace_path(), workspace)
        return workspace

    def load_workspace(self) -> Optional[dict]:
        """读取 workspace.json。
        Load workspace.json. Returns None if not found.
        """
        path = self._workspace_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Run 持久化 / Run persistence
    # ------------------------------------------------------------------

    def save_run(self, run: Run) -> None:
        """持久化 Run 快照，并将 run_id 登记到 workspace.json.run_ids。
        Persist Run snapshot and register run_id in workspace.json.run_ids.

        步骤 / Steps:
        1. 原子写 runs/run_{id}.json
        2. 更新 workspace.json run_ids（idempotent）

        Atomic per step; steps are NOT jointly atomic.
        """
        # Step 1: write run file
        self._atomic_write(self._run_path(run.run_id), run.model_dump())
        # Step 2: register in workspace
        ws = self._load_or_raise()
        if run.run_id not in ws["run_ids"]:
            ws["run_ids"].append(run.run_id)
        self._atomic_write(self._workspace_path(), ws)

    def load_run(self, run_id: str) -> Optional[Run]:
        """加载 Run 快照。
        Load Run snapshot. Returns None if not found.
        Raises ValueError on case_id mismatch or malformed JSON.
        """
        path = self._run_path(run_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("case_id") != self.case_id:
            raise ValueError(
                f"case_id mismatch in run_{run_id}.json: "
                f"expected {self.case_id!r}, got {data.get('case_id')!r}"
            )
        return Run.model_validate(data)

    # ------------------------------------------------------------------
    # 产物持久化 / Artifact persistence
    # ------------------------------------------------------------------

    def save_evidence_index(self, evidence_index: EvidenceIndex) -> None:
        """持久化证据索引，更新 material_index.Evidence。
        Persist EvidenceIndex and update material_index.Evidence refs.
        """
        storage_ref = "artifacts/evidence_index.json"
        path = self._artifacts_dir() / "evidence_index.json"
        self._atomic_write(path, evidence_index.model_dump())
        ws = self._load_or_raise()
        ws["material_index"]["Evidence"] = [
            {
                "object_type": "Evidence",
                "object_id": e.evidence_id,
                "storage_ref": storage_ref,
            }
            for e in evidence_index.evidence
        ]
        self._atomic_write(self._workspace_path(), ws)

    def save_claims_defenses(
        self, claims: list[Claim], defenses: list[Defense]
    ) -> None:
        """持久化诉请与抗辩，更新 material_index.Claim / Defense。
        Persist Claims and Defenses and update material_index entries.
        """
        storage_ref = "artifacts/claim_defense.json"
        data = {
            "case_id": self.case_id,
            "claims": [c.model_dump() for c in claims],
            "defenses": [d.model_dump() for d in defenses],
        }
        path = self._artifacts_dir() / "claim_defense.json"
        self._atomic_write(path, data)
        ws = self._load_or_raise()
        ws["material_index"]["Claim"] = [
            {
                "object_type": "Claim",
                "object_id": c.claim_id,
                "storage_ref": storage_ref,
            }
            for c in claims
        ]
        ws["material_index"]["Defense"] = [
            {
                "object_type": "Defense",
                "object_id": d.defense_id,
                "storage_ref": storage_ref,
            }
            for d in defenses
        ]
        self._atomic_write(self._workspace_path(), ws)

    def save_issue_tree(self, issue_tree: IssueTree) -> None:
        """持久化争点树，更新 material_index.Issue / Burden。
        Persist IssueTree and update material_index.Issue and Burden refs.
        """
        storage_ref = "artifacts/issue_tree.json"
        path = self._artifacts_dir() / "issue_tree.json"
        self._atomic_write(path, issue_tree.model_dump())
        ws = self._load_or_raise()
        ws["material_index"]["Issue"] = [
            {
                "object_type": "Issue",
                "object_id": i.issue_id,
                "storage_ref": storage_ref,
            }
            for i in issue_tree.issues
        ]
        ws["material_index"]["Burden"] = [
            {
                "object_type": "Burden",
                "object_id": b.burden_id,
                "storage_ref": storage_ref,
            }
            for b in issue_tree.burdens
        ]
        self._atomic_write(self._workspace_path(), ws)

    def save_report(self, report: ReportArtifact) -> None:
        """持久化报告产物，更新 artifact_index.ReportArtifact。
        Persist ReportArtifact and update artifact_index.ReportArtifact ref.
        """
        storage_ref = "artifacts/report.json"
        path = self._artifacts_dir() / "report.json"
        self._atomic_write(path, report.model_dump())
        ws = self._load_or_raise()
        ws["artifact_index"]["ReportArtifact"] = [
            {
                "object_type": "ReportArtifact",
                "object_id": report.report_id,
                "storage_ref": storage_ref,
            }
        ]
        self._atomic_write(self._workspace_path(), ws)

    def save_interaction_turn(self, turn: InteractionTurn) -> None:
        """持久化追问轮次，顺序追加到 artifact_index.InteractionTurn。
        Persist InteractionTurn and append to artifact_index.InteractionTurn.

        使用 artifact_index 中当前 InteractionTurn 数量计算顺序编号，
        保证 checkpoint resume 后编号仍然一致（不依赖目录扫描）。
        Sequential number derived from current InteractionTurn count in workspace.json
        so numbering stays consistent after checkpoint resume.
        """
        ws = self._load_or_raise()
        turn_num = len(ws["artifact_index"]["InteractionTurn"]) + 1
        filename = f"turn_{turn_num:03d}.json"
        storage_ref = f"artifacts/turns/{filename}"
        path = self._artifacts_dir() / "turns" / filename
        self._atomic_write(path, turn.model_dump())
        ws["artifact_index"]["InteractionTurn"].append(
            {
                "object_type": "InteractionTurn",
                "object_id": turn.turn_id,
                "storage_ref": storage_ref,
            }
        )
        self._atomic_write(self._workspace_path(), ws)

    def save_scenario_result(self, scenario: Scenario) -> None:
        """持久化场景结果，追加到 artifact_index.Scenario。
        Persist Scenario result and append to artifact_index.Scenario.
        """
        storage_ref = f"artifacts/scenarios/scenario_{scenario.scenario_id}.json"
        path = self._artifacts_dir() / "scenarios" / f"scenario_{scenario.scenario_id}.json"
        self._atomic_write(path, scenario.model_dump())
        ws = self._load_or_raise()
        ws["artifact_index"]["Scenario"].append(
            {
                "object_type": "Scenario",
                "object_id": scenario.scenario_id,
                "storage_ref": storage_ref,
            }
        )
        self._atomic_write(self._workspace_path(), ws)

    # ------------------------------------------------------------------
    # 产物加载 / Artifact loading（checkpoint resume）
    # ------------------------------------------------------------------

    def load_evidence_index(self) -> Optional[EvidenceIndex]:
        """加载证据索引。
        Load EvidenceIndex. Returns None if not found.
        Raises ValueError on case_id mismatch.
        """
        path = self._artifacts_dir() / "evidence_index.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("case_id") != self.case_id:
            raise ValueError(
                f"case_id mismatch in evidence_index.json: "
                f"expected {self.case_id!r}, got {data.get('case_id')!r}"
            )
        return EvidenceIndex.model_validate(data)

    def load_claims_defenses(
        self,
    ) -> Optional[tuple[list[Claim], list[Defense]]]:
        """加载诉请与抗辩。
        Load Claims and Defenses. Returns None if not found.
        Raises ValueError on case_id mismatch.
        """
        path = self._artifacts_dir() / "claim_defense.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("case_id") != self.case_id:
            raise ValueError(
                f"case_id mismatch in claim_defense.json: "
                f"expected {self.case_id!r}, got {data.get('case_id')!r}"
            )
        claims = [Claim.model_validate(c) for c in data["claims"]]
        defenses = [Defense.model_validate(d) for d in data["defenses"]]
        return claims, defenses

    def load_issue_tree(self) -> Optional[IssueTree]:
        """加载争点树。
        Load IssueTree. Returns None if not found.
        Raises ValueError on case_id mismatch.
        """
        path = self._artifacts_dir() / "issue_tree.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("case_id") != self.case_id:
            raise ValueError(
                f"case_id mismatch in issue_tree.json: "
                f"expected {self.case_id!r}, got {data.get('case_id')!r}"
            )
        return IssueTree.model_validate(data)

    def load_report(self) -> Optional[ReportArtifact]:
        """加载报告产物。
        Load ReportArtifact. Returns None if not found.
        Raises ValueError on case_id mismatch.
        """
        path = self._artifacts_dir() / "report.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("case_id") != self.case_id:
            raise ValueError(
                f"case_id mismatch in report.json: "
                f"expected {self.case_id!r}, got {data.get('case_id')!r}"
            )
        return ReportArtifact.model_validate(data)

    # ------------------------------------------------------------------
    # AgentOutput 持久化 / AgentOutput persistence
    # ------------------------------------------------------------------

    def save_agent_output(
        self,
        output: AgentOutput,
        access_domain: AccessDomain,
    ) -> str:
        """持久化 AgentOutput，按访问域路由到对应目录，更新 artifact_index.AgentOutput。
        Persist AgentOutput, route to directory by access_domain,
        and register in artifact_index.AgentOutput.

        路由规则 / Routing:
          owner_private   → artifacts/private/{owner_party_id}/agent_outputs/{output_id}.json
          shared_common   → artifacts/shared/agent_outputs/{output_id}.json
          admitted_record → artifacts/admitted/agent_outputs/{output_id}.json

        Returns:
            storage_ref 字符串 / storage_ref string
        """
        output_id = output.output_id
        owner = output.owner_party_id

        if access_domain == AccessDomain.owner_private:
            storage_ref = f"artifacts/private/{owner}/agent_outputs/{output_id}.json"
            path = (
                self._artifacts_dir()
                / "private" / owner / "agent_outputs"
                / f"{output_id}.json"
            )
        elif access_domain == AccessDomain.shared_common:
            storage_ref = f"artifacts/shared/agent_outputs/{output_id}.json"
            path = (
                self._artifacts_dir()
                / "shared" / "agent_outputs"
                / f"{output_id}.json"
            )
        elif access_domain == AccessDomain.admitted_record:
            storage_ref = f"artifacts/admitted/agent_outputs/{output_id}.json"
            path = (
                self._artifacts_dir()
                / "admitted" / "agent_outputs"
                / f"{output_id}.json"
            )
        else:
            raise ValueError(f"Unsupported access_domain: {access_domain!r}")

        self._atomic_write(path, output.model_dump())

        ws = self._load_or_raise()
        ws["artifact_index"]["AgentOutput"].append(
            {
                "object_type": "AgentOutput",
                "object_id": output_id,
                "storage_ref": storage_ref,
            }
        )
        self._atomic_write(self._workspace_path(), ws)
        return storage_ref

    def load_agent_output(self, output_id: str, storage_ref: str) -> Optional[AgentOutput]:
        """按 storage_ref 加载 AgentOutput。
        Load AgentOutput by storage_ref. Returns None if not found.
        Raises ValueError on case_id mismatch.
        """
        path = self.workspace_dir / storage_ref
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("case_id") != self.case_id:
            raise ValueError(
                f"case_id mismatch in {storage_ref}: "
                f"expected {self.case_id!r}, got {data.get('case_id')!r}"
            )
        return AgentOutput.model_validate(data)

    # ------------------------------------------------------------------
    # ExecutiveSummaryArtifact 持久化 / ExecutiveSummaryArtifact persistence  (P2.12)
    # ------------------------------------------------------------------

    def save_executive_summary(self, summary: ExecutiveSummaryArtifact) -> None:
        """持久化执行摘要产物，更新 artifact_index.ExecutiveSummaryArtifact。
        Persist ExecutiveSummaryArtifact and update artifact_index ref.
        """
        storage_ref = "artifacts/executive_summary.json"
        path = self._artifacts_dir() / "executive_summary.json"
        self._atomic_write(path, summary.model_dump())
        ws = self._load_or_raise()
        ws["artifact_index"]["ExecutiveSummaryArtifact"] = [
            {
                "object_type": "ExecutiveSummaryArtifact",
                "object_id": summary.summary_id,
                "storage_ref": storage_ref,
            }
        ]
        self._atomic_write(self._workspace_path(), ws)

    def load_executive_summary(self) -> Optional[ExecutiveSummaryArtifact]:
        """加载执行摘要产物。
        Load ExecutiveSummaryArtifact. Returns None if not found.
        Raises ValueError on case_id mismatch.
        """
        path = self._artifacts_dir() / "executive_summary.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("case_id") != self.case_id:
            raise ValueError(
                f"case_id mismatch in executive_summary.json: "
                f"expected {self.case_id!r}, got {data.get('case_id')!r}"
            )
        return ExecutiveSummaryArtifact.model_validate(data)

    # ------------------------------------------------------------------
    # 阶段推进 / Stage advancement
    # ------------------------------------------------------------------

    def advance_stage(self, stage: WorkflowStage) -> None:
        """推进工作流阶段，原子更新 workspace.json。
        Advance workflow stage; atomically update workspace.json.
        """
        ws = self._load_or_raise()
        ws["current_workflow_stage"] = (
            stage.value if isinstance(stage, WorkflowStage) else str(stage)
        )
        self._atomic_write(self._workspace_path(), ws)
