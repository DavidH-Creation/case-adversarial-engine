---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\progress_reporter.py"
type: "code"
community: "C: Users"
location: "L74"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# SSEProgressReporter

## Connections
- [[.__init__()_57]] - `method` [EXTRACTED]
- [[.close()]] - `method` [EXTRACTED]
- [[.on_error()_1]] - `method` [EXTRACTED]
- [[.on_step_complete()_1]] - `method` [EXTRACTED]
- [[.on_step_start()_1]] - `method` [EXTRACTED]
- [[Can add multiple materials to same case.]] - `uses` [INFERRED]
- [[Cannot analyze before confirmation.]] - `uses` [INFERRED]
- [[Cannot confirm before extraction.]] - `uses` [INFERRED]
- [[Drain all events from a progress queue synchronously.]] - `uses` [INFERRED]
- [[E2E create → materials → extract → extraction → confirm → analyze → result → re]] - `uses` [INFERRED]
- [[Each line is independently parseable JSON.]] - `uses` [INFERRED]
- [[Edge case pipeline fails at step 3 → error event then close.]] - `uses` [INFERRED]
- [[GET analysis on analyzed case returns SSE with type=done.]] - `uses` [INFERRED]
- [[GET analysis on created case returns SSE with type=error.]] - `uses` [INFERRED]
- [[GET analysis on nonexistent case returns 404.]] - `uses` [INFERRED]
- [[GET cases includes newly created cases.]] - `uses` [INFERRED]
- [[GET cases {id} returns correct info for a newly created case.]] - `uses` [INFERRED]
- [[GET export format=json returns a CaseSnapshot JSON.]] - `uses` [INFERRED]
- [[GET export format=markdown returns the report markdown body.]] - `uses` [INFERRED]
- [[GET progress on case with no progress queue returns 404.]] - `uses` [INFERRED]
- [[GET progress on case with registered queue returns SSE stream.]] - `uses` [INFERRED]
- [[GET result on non-analyzed case returns status but no run_id.]] - `uses` [INFERRED]
- [[Happy path 5-step pipeline → 5 'completed' lines in order.]] - `uses` [INFERRED]
- [[Minimal analysis_data matching AnalysisResponse schema.]] - `uses` [INFERRED]
- [[Minimal extraction data matching ExtractionResponse schema.]] - `uses` [INFERRED]
- [[Missing case_type should return 422 (Pydantic validation).]] - `uses` [INFERRED]
- [[Mock analysis that injects fake data without calling LLM.]] - `uses` [INFERRED]
- [[Mock extraction that injects fake data without calling LLM.]] - `uses` [INFERRED]
- [[POST extract on a case with no materials must return 400. Pinned to]] - `uses` [INFERRED]
- [[Parse SSE response body into list of JSON event dicts.]] - `uses` [INFERRED]
- [[Poll the test store until the case reaches `target` (or raise on timeout).]] - `uses` [INFERRED]
- [[ProgressReporter]] - `inherits` [EXTRACTED]
- [[Push a case through the full lifecycle to analyzed state. Returns case_id.]] - `uses` [INFERRED]
- [[Pushes structured JSON step events to a per-run asyncio.Queue for SSE streaming.]] - `rationale_for` [EXTRACTED]
- [[Response includes char_count for the added material.]] - `uses` [INFERRED]
- [[SSE 5-step pipeline pushes 5 completed + 1 done sentinel.]] - `uses` [INFERRED]
- [[TestCLIProgressReporter]] - `uses` [INFERRED]
- [[TestClient with isolated workspace, no auth, mocked extraction + analysis.]] - `uses` [INFERRED]
- [[TestErrorHandling]] - `uses` [INFERRED]
- [[TestExport]] - `uses` [INFERRED]
- [[TestFullLifecycle]] - `uses` [INFERRED]
- [[TestJSONProgressReporter]] - `uses` [INFERRED]
- [[TestMaterials]] - `uses` [INFERRED]
- [[TestSSEEndpoints]] - `uses` [INFERRED]
- [[TestSSEProgressReporter]] - `uses` [INFERRED]
- [[TestStateMachine]] - `uses` [INFERRED]
- [[Tests for engines shared progress_reporter.py Covers - CLIProgressReporte]] - `uses` [INFERRED]
- [[Unit B E2E API lifecycle tests — full pipeline through HTTP endpoints. Tests]] - `uses` [INFERRED]
- [[Verify API rejects operations when case is in wrong state.]] - `uses` [INFERRED]
- [[Verify API returns proper errors for invalid inputs.]] - `uses` [INFERRED]
- [[Verify SSE streaming endpoints return correct event-stream format.]] - `uses` [INFERRED]
- [[Verify export endpoints on analyzed cases.]] - `uses` [INFERRED]
- [[Verify material upload and storage.]] - `uses` [INFERRED]
- [[progress_reporter.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/C:_Users