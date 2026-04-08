---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\checkpoint.py"
type: "code"
community: "C: Users"
location: "L48"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# CheckpointManager

## Connections
- [[.__init__()_47]] - `method` [EXTRACTED]
- [[.clear()]] - `method` [EXTRACTED]
- [[.load()_1]] - `method` [EXTRACTED]
- [[.save()_1]] - `method` [EXTRACTED]
- [[.validate_artifacts()]] - `method` [EXTRACTED]
- [[Add case_id and owner_party_id to claim dicts.]] - `uses` [INFERRED]
- [[Add case_id and owner_party_id to defense dicts.]] - `uses` [INFERRED]
- [[After a full run, last_completed_step is the final step.]] - `uses` [INFERRED]
- [[Both first-run and resume must produce the same lint outcome.]] - `uses` [INFERRED]
- [[Build EvidenceGapDescriptor list for P1.7 from two sources 1. Rule-based]] - `uses` [INFERRED]
- [[Build a FourLayerReport with enough content to survive the 0.20 gate.]] - `uses` [INFERRED]
- [[CheckpointState dataclass behavior.]] - `uses` [INFERRED]
- [[CheckpointState with report_v3_json returns has_v3_artifacts=True.]] - `uses` [INFERRED]
- [[CheckpointState without report_v3_json returns has_v3_artifacts=False.]] - `uses` [INFERRED]
- [[Checkpoints without v3 artifact keys must still work.]] - `uses` [INFERRED]
- [[Convert YAML financials section to AmountCalculatorInput. Returns None if no fin]] - `uses` [INFERRED]
- [[Convert YAML material dicts to RawMaterial objects.]] - `uses` [INFERRED]
- [[Derive evidence gap indicators from pretrial cross-examination results. U]] - `uses` [INFERRED]
- [[First write_v3_report_md and rebuild_from_artifacts produce same headings.]] - `uses` [INFERRED]
- [[First-run and resume must produce structurally identical reports.]] - `uses` [INFERRED]
- [[FourLayerReport JSON serialization survives rebuild.]] - `uses` [INFERRED]
- [[Load and validate a YAML case file.]] - `uses` [INFERRED]
- [[Load pipeline section from config.yaml at project root. Returns {} if missing.]] - `uses` [INFERRED]
- [[Manages checkpoint persistence for a single pipeline run. Usage]] - `rationale_for` [EXTRACTED]
- [[Phase 4 Resume & idempotency tests for rebuild_from_artifacts(). Tests 1]] - `uses` [INFERRED]
- [[Rebuilt report must pass the render contract (10 rules).]] - `uses` [INFERRED]
- [[Relative paths are resolved relative to the output directory.]] - `uses` [INFERRED]
- [[Return True if step was already completed according to checkpoint.]] - `uses` [INFERRED]
- [[Return a temporary output directory for a single run.]] - `uses` [INFERRED]
- [[Run 3-round adversarial debate.]] - `uses` [INFERRED]
- [[Run post-debate analysis pipeline. Returns dict of all artifacts.]] - `uses` [INFERRED]
- [[Save and load a v2 checkpoint — no v3 keys should appear.]] - `uses` [INFERRED]
- [[Save and load a v3 checkpoint — v3 keys must survive round-trip.]] - `uses` [INFERRED]
- [[Serialize a FourLayerReport to disk, rebuild, verify no LLM calls.]] - `uses` [INFERRED]
- [[Serialize → deserialize must preserve all fields.]] - `uses` [INFERRED]
- [[Simulate the checkpoint + resume flow without actual LLM calls.]] - `uses` [INFERRED]
- [[Successive saves accumulate artifact paths.]] - `uses` [INFERRED]
- [[Test the step-skip logic used during resume.]] - `uses` [INFERRED]
- [[TestCheckpointBackwardCompat]] - `uses` [INFERRED]
- [[TestCheckpointState]] - `uses` [INFERRED]
- [[TestClear]] - `uses` [INFERRED]
- [[TestCorruptCheckpoint]] - `uses` [INFERRED]
- [[TestJsonRoundTrip]] - `uses` [INFERRED]
- [[TestLoadNone]] - `uses` [INFERRED]
- [[TestRebuildZeroLLM]] - `uses` [INFERRED]
- [[TestResumeIdempotency]] - `uses` [INFERRED]
- [[TestResumeIntegration]] - `uses` [INFERRED]
- [[TestResumeRenderContract]] - `uses` [INFERRED]
- [[TestSaveAndLoad]] - `uses` [INFERRED]
- [[TestShouldSkip]] - `uses` [INFERRED]
- [[TestValidateArtifacts]] - `uses` [INFERRED]
- [[Tests for engines.shared.checkpoint — CheckpointManager.]] - `uses` [INFERRED]
- [[Write checkpoint from one manager, read from another.]] - `uses` [INFERRED]
- [[checkpoint.py]] - `contains` [EXTRACTED]
- [[clear() is a no-op when there's nothing to clear.]] - `uses` [INFERRED]
- [[rebuild_from_artifacts raises FileNotFoundError without report_v3.json.]] - `uses` [INFERRED]
- [[rebuild_from_artifacts() must not invoke any LLM client.]] - `uses` [INFERRED]
- [[save() persists state; load() recovers it.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/C:_Users