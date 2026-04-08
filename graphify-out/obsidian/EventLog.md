---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\event_log.py"
type: "code"
community: "C: Users"
location: "L47"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# EventLog

## Connections
- [[.__init__()_52]] - `method` [EXTRACTED]
- [[.append()]] - `method` [EXTRACTED]
- [[.load_all()_1]] - `method` [EXTRACTED]
- [[.load_since()]] - `method` [EXTRACTED]
- [[Append one event to events.jsonl (thread-safe).]] - `uses` [INFERRED]
- [[Load a JSON artifact from artifacts .]] - `uses` [INFERRED]
- [[Load a UTF-8 text artifact from artifacts .]] - `uses` [INFERRED]
- [[Load a binary artifact from artifacts .]] - `uses` [INFERRED]
- [[Load case_meta.json from workspace directory. Returns None if not found]] - `uses` [INFERRED]
- [[Load events from events.jsonl, optionally after a marker event.]] - `uses` [INFERRED]
- [[Persist a JSON artifact under artifacts using an atomic write.]] - `uses` [INFERRED]
- [[Persist a UTF-8 text artifact under artifacts .]] - `uses` [INFERRED]
- [[Persist a binary artifact under artifacts .]] - `uses` [INFERRED]
- [[Persist case_meta.json to workspace directory (atomic write). 持久化案件元数据（]] - `uses` [INFERRED]
- [[Raise ValueError if value contains characters outside a-zA-Z0-9_ -.]] - `uses` [INFERRED]
- [[Raise ValueError if value is not a safe artifact filename.]] - `uses` [INFERRED]
- [[Return the path for a top-level artifact file inside artifacts .]] - `uses` [INFERRED]
- [[Save artifact with version history. Before overwriting, rename the ex]] - `uses` [INFERRED]
- [[Tests for engines shared event_log.py — append-only JSONL event log.]] - `uses` [INFERRED]
- [[Thread-safe append-only JSONL event log. Storage {workspace_dir} {case_i]] - `rationale_for` [EXTRACTED]
- [[Verify all CaseEvent fields survive JSONL serialization.]] - `uses` [INFERRED]
- [[WorkspaceManager]] - `uses` [INFERRED]
- [[event_log.py]] - `contains` [EXTRACTED]
- [[初始化工作区：创建目录结构和初始 workspace.json。 Initialize workspace create directory]] - `uses` [INFERRED]
- [[加载 Run 快照。 Load Run snapshot. Returns None if not found. Raise]] - `uses` [INFERRED]
- [[加载争点树。 Load IssueTree. Returns None if not found. Raises Value]] - `uses` [INFERRED]
- [[加载执行摘要产物。 Load ExecutiveSummaryArtifact. Returns None if not found.]] - `uses` [INFERRED]
- [[加载报告产物。 Load ReportArtifact. Returns None if not found. Raises]] - `uses` [INFERRED]
- [[加载证据索引。 Load EvidenceIndex. Returns None if not found. Raises]] - `uses` [INFERRED]
- [[加载诉请与抗辩。 Load Claims and Defenses. Returns None if not found.]] - `uses` [INFERRED]
- [[原子写操作：先写 .tmp 文件，再重命名替换目标。 Atomic write write to .tmp file then rename]] - `uses` [INFERRED]
- [[持久化 AgentOutput，按访问域路由到对应目录，更新 artifact_index.AgentOutput。 Persist Agen]] - `uses` [INFERRED]
- [[持久化 Run 快照，并将 run_id 登记到 workspace.json.run_ids。 Persist Run snapshot a]] - `uses` [INFERRED]
- [[持久化争点树，更新 material_index.Issue Burden。 Persist IssueTree and update m]] - `uses` [INFERRED]
- [[持久化场景结果，追加到 artifact_index.Scenario。 Persist Scenario result and append]] - `uses` [INFERRED]
- [[持久化执行摘要产物，更新 artifact_index.ExecutiveSummaryArtifact。 Persist Executive]] - `uses` [INFERRED]
- [[持久化报告产物，更新 artifact_index.ReportArtifact。 Persist ReportArtifact and up]] - `uses` [INFERRED]
- [[持久化证据索引，更新 material_index.Evidence。 Persist EvidenceIndex and update ma]] - `uses` [INFERRED]
- [[持久化诉请与抗辩，更新 material_index.Claim Defense。 Persist Claims and Defenses]] - `uses` [INFERRED]
- [[持久化追问轮次，顺序追加到 artifact_index.InteractionTurn。 Persist InteractionTurn a]] - `uses` [INFERRED]
- [[按 storage_ref 加载 AgentOutput。 Load AgentOutput by storage_ref. Returns]] - `uses` [INFERRED]
- [[推进工作流阶段，原子更新 workspace.json。 Advance workflow stage; atomically update]] - `uses` [INFERRED]
- [[构造初始 workspace.json 内容（run_ids 为空）。 Build initial workspace.json conten]] - `uses` [INFERRED]
- [[案件工作区管理器 — 统一持久化入口。 WorkspaceManager — single persistence entry point for CaseW]] - `uses` [INFERRED]
- [[案件工作区读写管理器。 CaseWorkspace read write manager. 目录结构 Directory layou]] - `uses` [INFERRED]
- [[读取 workspace.json。 Load workspace.json. Returns None if not found.]] - `uses` [INFERRED]
- [[读取 workspace.json；若不存在则抛 ValueError。 Load workspace.json; raise ValueEr]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users