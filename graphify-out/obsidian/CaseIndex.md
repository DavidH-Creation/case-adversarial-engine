---
source_file: "C:\Users\david\dev\case-adversarial-engine\api\case_index.py"
type: "code"
community: "C: Users"
location: "L30"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# CaseIndex

## Connections
- [[.__init__()]] - `method` [EXTRACTED]
- [[.query()]] - `method` [EXTRACTED]
- [[.remove()]] - `method` [EXTRACTED]
- [[.scan_from_disk()]] - `method` [EXTRACTED]
- [[.upsert()]] - `method` [EXTRACTED]
- [[Atomically flush the in-memory record for case_id to case_meta.json.]] - `uses` [INFERRED]
- [[Build a CaseIndexEntry from a live CaseRecord.]] - `uses` [INFERRED]
- [[CaseIndex 单元测试。 Unit tests for CaseIndex scan_from_disk, upsert, remove, query]] - `uses` [INFERRED]
- [[CaseRecord]] - `uses` [INFERRED]
- [[CaseScenarioManager]] - `uses` [INFERRED]
- [[CaseStore]] - `uses` [INFERRED]
- [[Create a followup job and launch it asynchronously. Returns job_id.]] - `uses` [INFERRED]
- [[Create a scenario job and launch it asynchronously. Returns scenario_id.]] - `uses` [INFERRED]
- [[Create an index with 5 cases for filter sort pagination tests.]] - `uses` [INFERRED]
- [[Emit audit event to the case's events.jsonl (non-fatal on failure).]] - `uses` [INFERRED]
- [[Execute the followup via FollowupResponder and store result.]] - `uses` [INFERRED]
- [[Execute the scenario via ScenarioService and store the result.]] - `uses` [INFERRED]
- [[FollowupJobManager]] - `uses` [INFERRED]
- [[In-memory case index. Rebuilt on startup via scan_from_disk(); kept curre]] - `rationale_for` [EXTRACTED]
- [[Invalid case_meta.json should be skipped, not crash the scan.]] - `uses` [INFERRED]
- [[Manages async followup Q&A jobs. Uses asyncio.create_task to run Followup]] - `uses` [INFERRED]
- [[Manages async scenario jobs scoped to a specific case. Uses asyncio.creat]] - `uses` [INFERRED]
- [[Public alias for _load_from_disk — reconstruct a CaseRecord from workspace.]] - `uses` [INFERRED]
- [[Reconstruct a CaseRecord from workspace persistence (restart recovery).]] - `uses` [INFERRED]
- [[Return all scenario jobs for a given case_id.]] - `uses` [INFERRED]
- [[Return followup job state, or None if not found.]] - `uses` [INFERRED]
- [[Return scenario job state, or None if not found.]] - `uses` [INFERRED]
- [[SSE 用异步生成器 — 先回放历史进度，再跟踪实时进度。]] - `uses` [INFERRED]
- [[Scan two case_meta.json files and rebuild the in-memory index.]] - `uses` [INFERRED]
- [[ScenarioService]] - `uses` [INFERRED]
- [[Serialize durable CaseRecord fields for workspace persistence.]] - `uses` [INFERRED]
- [[Write durable CaseRecord state to workspace (non-fatal on failure).]] - `uses` [INFERRED]
- [[case_index.py]] - `contains` [EXTRACTED]
- [[has_report is True when artifact_names contains report.docx.]] - `uses` [INFERRED]
- [[业务逻辑层 — 桥接 FastAPI 和现有对抗式分析引擎。 Service layer — bridges FastAPI endpoints and th]] - `uses` [INFERRED]
- [[从 WorkspaceManager 持久化存储中恢复 CaseRecord。]] - `uses` [INFERRED]
- [[从 analysis_data 和 case info 生成 Markdown 格式报告。]] - `uses` [INFERRED]
- [[从 outputs {run_id} 加载 baseline，执行场景推演，返回序列化的 ScenarioResult。]] - `uses` [INFERRED]
- [[单案件的运行时状态容器。线程 任务安全性由 asyncio 单线程保证。]] - `uses` [INFERRED]
- [[封装 ScenarioSimulator 调用，管理场景结果的存储和查询。]] - `uses` [INFERRED]
- [[将 CaseRecord.info 转换为 generate_docx_report 期望的 case_data dict。]] - `uses` [INFERRED]
- [[异步后台任务：三轮对抗辩论 + LLM 总结 + 生成 DOCX 报告。]] - `uses` [INFERRED]
- [[查询已运行 scenario 的结果（先查内存，再查磁盘）。]] - `uses` [INFERRED]
- [[清理过期条目，返回清理数量。保存最后状态到磁盘后再删除。]] - `uses` [INFERRED]
- [[返回具体产物内容，不存在时返回 None。]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users