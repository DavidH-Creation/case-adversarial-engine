# Graph Report - C:\Users\david\dev\case-adversarial-engine  (2026-04-08)

## Corpus Check
- Large corpus: 591 files · ~436,733 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 7509 nodes · 26486 edges · 117 communities detected
- Extraction: 28% EXTRACTED · 72% INFERRED · 0% AMBIGUOUS · INFERRED: 18982 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `SectionTag` - 270 edges
2. `EvidenceBasicCard` - 226 edges
3. `Layer3Perspective` - 207 edges
4. `EvidencePriority` - 205 edges
5. `场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.` - 204 edges
6. `PerspectiveOutput` - 204 edges
7. `AdversarialResult` - 203 edges
8. `TimelineEvent` - 201 edges
9. `Layer4Appendix` - 197 edges
10. `CaseStatus` - 195 edges

## Surprising Connections (you probably didn't know these)
- `集成测试共享 fixtures 和 Mock 工具。 Shared fixtures and mock utilities for integration t` --uses--> `CaseStatus`  [INFERRED]
  C:\Users\david\dev\case-adversarial-engine\tests\integration\conftest.py → C:\Users\david\dev\case-adversarial-engine\api\schemas.py
- `TestClient with isolated workspace dir, no auth required.` --uses--> `CaseStatus`  [INFERRED]
  C:\Users\david\dev\case-adversarial-engine\api\tests\conftest.py → C:\Users\david\dev\case-adversarial-engine\api\schemas.py
- `TestClient with test users.json + JWT signing key configured.` --uses--> `CaseStatus`  [INFERRED]
  C:\Users\david\dev\case-adversarial-engine\api\tests\conftest.py → C:\Users\david\dev\case-adversarial-engine\api\schemas.py
- `Create a case using admin JWT and return case_id.` --uses--> `CaseStatus`  [INFERRED]
  C:\Users\david\dev\case-adversarial-engine\api\tests\conftest.py → C:\Users\david\dev\case-adversarial-engine\api\schemas.py
- `DefendantAgent — 被告代理人，生成抗辩和反驳。 DefendantAgent — defendant party agent, generat` --uses--> `BasePartyAgent`  [INFERRED]
  C:\Users\david\dev\case-adversarial-engine\engines\adversarial\agents\defendant.py → C:\Users\david\dev\case-adversarial-engine\engines\adversarial\agents\base_agent.py

## Communities

### Community 0 - "C: Users"
Cohesion: 0.01
Nodes (754): AccessController, 证据可见性过滤器。 Evidence visibility filter. 将完整证据列表按角色编码和所属方 party_id 过滤，返, Issue, AgentOutputValidationError, BasePartyAgent, 生成反驳轮输出。Generate rebuttal round output., 调用 LLM（带重试）并验证输出为合法 AgentOutput。 Call LLM with unified retry loop and v, 将 LLM JSON 输出解析为 AgentOutput。 Parse LLM JSON output dict to AgentOutput (+746 more)

### Community 1 - "C: Users"
Cohesion: 0.03
Nodes (448): CheckpointManager, CheckpointState, Checkpoint manager for pipeline resume support. Saves loads checkpoint state, Load checkpoint from disk. Returns CheckpointState if a, Remove the checkpoint file if it exists., Check that all artifact files referenced by the checkpoint exist. Ret, Deserialized checkpoint data., Manages checkpoint persistence for a single pipeline run. Usage (+440 more)

### Community 2 - "C: Users"
Cohesion: 0.01
Nodes (365): PretrialConferenceEngine, 庭前会议编排器 — v1.5 顶层组件。 Pretrial conference engine — v1.5 top-level orchestrator., 庭前会议编排器。 Args llm_client 符合 LLMClient 协议的客户端实例 model, 执行庭前会议全流程。 Args issue_tree 争点树, CrossExaminationEngine, 质证编排器 — v1.5 核心组件。 Cross-examination engine — v1.5 core component. 职责 Resp, 调用 LLM 对一批证据进行质证，返回校验后的意见列表。, 解析 LLM 输出并校验，返回合法意见列表。 (+357 more)

### Community 3 - "C: Users"
Cohesion: 0.01
Nodes (328): AlternativeClaimGenerator, _classify_phase(), _compute_path_ranking(), DecisionPathTreeGenerator, _derive_alternative_text(), _derive_evidence_ids_from_issues(), _derive_stability_rationale(), _dfs_find_cycle() (+320 more)

### Community 4 - "C: Users"
Cohesion: 0.01
Nodes (299): FastAPI application for the case adversarial analysis service., BasePartyAgent — 共享 LLM 调用逻辑的基类。 BasePartyAgent — base class with shared LLM ca, BaseModel, AmountCalculationReport, AmountConflict, AmountConsistencyCheck, build_cross_exam_user_prompt(), build_user_prompt() (+291 more)

### Community 5 - "C: Users"
Cohesion: 0.02
Nodes (233): AmountCalculator, AmountCalculator — 金额 诉请一致性硬校验模块。 Amount claim consistency hard validation modu, 构建诉请计算表。 principal 类诉请：calculated_amount = 总放款基数 - 总还款（归因 principal）。, 计算 principal_base_contribution=True 的放款总额。, 计算归因 principal 的已还款总额。, 计算应还本金 = principal 放款总额 - 已还本金总额。, 本金基数唯一性：当且仅当不存在 unresolved 的争议归因条目时返回 True。 逻辑：若存在任何 resolution_statu, 所有还款均已归因（attributed_to 非 None）时返回 True。 (+225 more)

### Community 6 - "C: Users"
Cohesion: 0.02
Nodes (212): Exception, _build_next_state_ids(), _load_prompt_module(), _make_state_id(), ProcedurePlanner, 程序设置引擎核心模块 Procedure setup engine core module. 根据案件类型（case_type）、当事人信息（parti, 程序设置规划器 Procedure Planner. 输入 ProcedureSetupInput + IssueTree，输出 Pro, 加载案由对应的 prompt 模板模块。 Load prompt template module for the given case typ (+204 more)

### Community 7 - "C: Users"
Cohesion: 0.03
Nodes (184): CaseExtractor, 加载案由对应的 prompt 模板模块。 Load the prompt template module for the given case, Call LLM with structured output, falling back to text extraction., Convert LLM output to pipeline-compatible ExtractedCase., Serialize ExtractedCase to YAML string. Args extracted, Validate extracted case against pipeline requirements. Returns, Load a prompt module from the registry., Convert text to a URL-friendly slug. (+176 more)

### Community 8 - "C: Users"
Cohesion: 0.03
Nodes (151): _build_item(), _compute_composite_score(), EvidenceGapROIRanker, IssueImpactRanker, _load_prompt_module(), _normalize_evaluation_keys(), _normalize_single_eval(), IssueImpactRanker — 争点影响排序模块主类。 Issue Impact Ranker — main class for P0.1 issue (+143 more)

### Community 9 - "C: Users"
Cohesion: 0.03
Nodes (127): append_document_draft_sections(), 报告生成器 Report Generator. 输入 IssueTree + EvidenceIndex，输出结构化 ReportArt, 加载案由对应的 prompt 模板模块。 Load prompt template module for the given case typ, 验证输入数据合法性。 Validate input data validity. Raises, 执行报告生成。 Execute report generation. Args issue_, 构建矩阵并作为额外章节附加到报告。 Build the matrix and attach it as an extra section to, 调用 LLM（结构化输出）。 Call LLM with structured output. Raises, 将 LLM 输出规范化为 ReportArtifact。 Normalize LLM output into a ReportArtifact (+119 more)

### Community 10 - "C: Users"
Cohesion: 0.01
Nodes (88): _load_fixture(), load_fixtures(), 合约测试 — 使用 benchmark fixtures 验证 Scenario Engine 的输出结构。 Contract tests — validat, 每条关键结论必须有至少一个 supporting_evidence_ids（citation_completeness=100%）。, baseline anchor 的 affected_issue_ids 和 affected_evidence_ids 必须为空。, 每个 ProcedureState 必须包含所有必填字段。, statement_class 必须为合法枚举值。, 所有 Evidence 的 case_id 应与输入一致。 (+80 more)

### Community 11 - "C: Users"
Cohesion: 0.06
Nodes (134): AdmissibilityEvaluator, AdmissibilityEvaluator — 证据可采性评估模块主类。 Admissibility Evaluator — main class for, 调用 LLM，失败时返回 None（不抛异常）。, 解析 LLM 输出 JSON，失败时返回 None。, 规则层：校验 LLM 输出，返回 evidence_id → 已校验字段字典的映射。 过滤规则： 1. evidence, 证据可采性评估器。 Args llm_client 符合 LLMClient 协议的客户端实例 case, 对证据索引中的所有证据进行可采性评估。 Args inp 评估器输入 Returns, _analyze_chain_impacts() (+126 more)

### Community 12 - "C: Users"
Cohesion: 0.17
Nodes (139): ActionRecommendation, AgentOutput, AlternativeClaimSuggestion, Burden, Claim, ClaimAbandonSuggestion, ClaimAmendmentSuggestion, ClaimDecomposition (+131 more)

### Community 13 - "C: Users"
Cohesion: 0.05
Nodes (116): AttackChainOptimizer, 调用 LLM（结构化输出），失败时返回 None（不抛异常）。, Normalize alternative field names LLM may use for attack chain output., 规范化 LLM 输出 dict，失败时返回 None。, 规则层处理攻击节点列表，返回最多 _MAX_ATTACKS 个有效节点。 过滤规则： 1. attack_node_id, LLM 失败时返回空 OptimalAttackChain。, 最强攻击链生成器。 Args llm_client 符合 LLMClient 协议的客户端实例 case, 生成最强攻击链。 Args inp 优化器输入 Returns (+108 more)

### Community 14 - "C: Users"
Cohesion: 0.03
Nodes (42): AccessViolationError, _is_visible(), 访问控制器 — 证据可见性过滤的单一入口。 AccessController — single entry point for evidence visibi, 返回该角色可见的证据子集（保持原顺序）。 Return the visible evidence subset for the given a, 判断单条证据对该角色是否可见。 Determine if a single evidence is visible to the given role, 未授权的访问尝试。Unauthorized access attempt. 当 role_code 不在已知角色映射表中时抛出。 Rai, IllegalTransitionError, 证据生命周期状态机 — v1.5 核心基础设施。 Evidence lifecycle state machine — v1.5 core infrastru (+34 more)

### Community 15 - "C: Users"
Cohesion: 0.04
Nodes (47): _build_best_attack(), build_evidence_battle_matrix(), build_evidence_cards(), _build_failure_impact(), _build_key_risk(), _build_q2_target(), _build_reinforce_strategy(), _evidence_stability_light() (+39 more)

### Community 16 - "C: Users"
Cohesion: 0.04
Nodes (42): CaseTypePlugin, CaseTypePlugin Protocol + UnsupportedCaseTypeError. Formalizes the PROMPT_REG, Return the built user prompt for the given case type. Raises, Return the per-case-type ``ALLOWED_IMPACT_TARGETS`` set. Looks up the, Raised when a case type is not registered in a CaseTypePlugin., Protocol for case-type-specific prompt generation. Each simulation_run en, Build and return the user prompt for the given case type. Args, Return the legal vocabulary for ``Issue.impact_targets`` for case_type . (+34 more)

### Community 17 - "C: Users"
Cohesion: 0.04
Nodes (38): _make_action_recommendation(), _make_agent_output(), _make_amount_report(), _make_attack_chain(), _make_attack_node(), _make_full_input(), _make_gap_item(), _make_issue() (+30 more)

### Community 18 - "C: Users"
Cohesion: 0.04
Nodes (32): JobManager, JobManager — 长任务生命周期管理器。 JobManager — long-running job lifecycle manager. 职责, 内部状态迁移：验证合法性，更新字段，持久化，返回新 Job。 field_overrides 中的值会覆盖 model_dump() 中对, 创建并持久化新 Job（初始状态：created，progress=0.0）。 Create and persist a new Job (i, 从磁盘加载 Job。若文件不存在，返回 None。 Load Job from disk. Returns None if the file, 返回当前 {workspace_dir} jobs 下所有 Job（按文件名排序）。 Return all Jobs under {work, created pending → running。, running → pending（中断 checkpoint）。 Running → pending (interrupt checkpoi (+24 more)

### Community 19 - "C: Users"
Cohesion: 0.04
Nodes (48): add_material_json(), _build_scenario_diff_response(), confirm_extraction(), create_case_scenario(), create_followup(), download_report(), export_case(), get_case() (+40 more)

### Community 20 - "C: Users"
Cohesion: 0.06
Nodes (73): _add_run(), _agent_color(), _build_issue_info(), _build_party_zh(), _bullet(), _filter_uuids(), generate_docx_report(), generate_docx_v3_report() (+65 more)

### Community 21 - "C: Users"
Cohesion: 0.05
Nodes (67): _abandon_reason(), ActionRecommender, _align_with_path_tree(), _amendment_description(), _annotate_path_ids(), _detect_dispute_category(), _explanation_text(), _inject_category_specific_actions() (+59 more)

### Community 22 - "C: Users"
Cohesion: 0.06
Nodes (69): _make_agent_output(), _make_burden(), _make_claim(), _make_defense(), _make_evidence(), _make_evidence_index(), _make_issue(), _make_issue_tree() (+61 more)

### Community 23 - "C: Users"
Cohesion: 0.06
Nodes (14): _artifact_ref(), _base_agent_output(), _base_job(), _job_error(), _now(), Job 模型单元测试 — JobStatus JobError Job AgentOutput。 Job model unit tests — J, TestAgentOutputInvariantViolations, TestAgentOutputRoundtrip (+6 more)

### Community 24 - "C: Users"
Cohesion: 0.1
Nodes (60): IssueCategoryClassifier, _load_prompt_module(), IssueCategoryClassifier — 争点类型分类模块主类。 Issue Category Classifier — main class fo, 将 LLM 分类结果校验后富化到 Issue 对象。 校验失败规则（任一失败 → 清空 issue_category，记入 unclass, 调用 LLM（结构化输出），失败时抛出异常由 classify() 捕获。, 争点类型分类器。 Args llm_client 符合 LLMClient 协议的客户端实例 case_, 执行争点类型分类。 Args inp 分类器输入（含争点树、证据索引、金额报告） Re, _resolve_issue_category() (+52 more)

### Community 25 - "C: Users"
Cohesion: 0.04
Nodes (40): _count_docx_headings(), _count_md_h2(), Assert V3 DOCX heading count = MD ## heading count., DOCX must contain at least as many heading sections as MD ## count., DOCX must contain headings for all four layers., DOCX layer1 should render A B C D E subsections when data is present., DOCX layer2 should render 2.1 fact_base, 2.2 issue_map, 2.4 evidence_cards., DOCX layer3 should have both plaintiff and defendant strategy sections. (+32 more)

### Community 26 - "C: Users"
Cohesion: 0.06
Nodes (32): _build_defendant_card(), _build_neutral_card(), build_perspective_card(), _build_plaintiff_card(), _filter_actions(), _get_paths(), 角色化视角模块 — 纯数据变换，不调用 LLM。 Perspective summary module — pure data transformation,, Render the cover summary perspective card (Layer 1 Block B). Returns a co (+24 more)

### Community 27 - "C: Users"
Cohesion: 0.06
Nodes (31): get_token_tracker(), JsonFormatter, LLMCallRecord, 结构化日志配置 — StructuredLogger wrapper，输出 JSON 格式日志。 Structured logging configurati, 获取全局 TokenTracker 实例 Get the global TokenTracker instance., 重置全局 TokenTracker（用于测试或新 pipeline） Reset global tracker., 将 logging.LogRecord 格式化为 JSON 行 Formats LogRecord as JSON lines., 初始化结构化 JSON 日志，输出到文件和 stderr。 Initialize structured JSON logging to file an (+23 more)

### Community 28 - "C: Users"
Cohesion: 0.05
Nodes (24): _from_dict(), from_yaml(), ModelTier, Multi-model tiered strategy — select haiku sonnet opus by task complexity. Mult, custom_config(), default_config(), Tests for engines.shared.model_selector — ModelSelector + ModelTier., When model_override is set, select() always returns it. (+16 more)

### Community 29 - "C: Users"
Cohesion: 0.06
Nodes (32): _make_action_rec(), _make_amount_report(), _make_attack_chain(), _make_decision_tree(), _make_exec_summary(), _make_ranked_issues(), _make_result(), Unit 11 报告增强集成测试 — 测试 _write_md 中新增的四个 section。 Integration tests for report en (+24 more)

### Community 30 - "C: Users"
Cohesion: 0.07
Nodes (17): _make_artifact(), engines shared tests test_models_p2_12.py ExecutiveSummaryArtifact 模型合约测试（P2., amount_report_id is Optional — empty string is valid (no longer required)., amount_report_id is Optional — None is the default., v7 current_most_stable_claim 已废弃，空字符串不再报错（向后兼容）。, top3_immediate_actions 为 list 时，action_recommendation_id 必须非 None。, top3_immediate_actions 为 未启用 时，action_recommendation_id 可以为 None。, top3_immediate_actions 为空 list 时，action_recommendation_id 也必须非 None。 (+9 more)

### Community 31 - "C: Users"
Cohesion: 0.09
Nodes (9): _make_failed_run(), _make_valid_run(), _make_yaml_file(), v2 multi-case acceptance test suite. Tests use mock pipeline results to verify, TestComputeMetrics, TestLoadAndValidateYaml, TestRunAcceptance, TestRunAcceptanceForCase (+1 more)

### Community 32 - "C: Users"
Cohesion: 0.07
Nodes (26): SessionState, 加载已有会话，或创建新会话。 Load existing session, or create a new one. A, 追加一轮追问并持久化。 Append a turn and persist the session. Args, 持久化会话状态到 JSON 文件。 Persist session state to JSON file., 多轮追问会话管理器。 Multi-turn followup session manager. 管理会话的创建、持久化和轮次追加。会话状, 会话文件路径 Session file path., 创建新会话并持久化。 Create a new session and persist it. Args, 加载已有会话。 Load an existing session. Returns Sess (+18 more)

### Community 33 - "C: Users"
Cohesion: 0.1
Nodes (26): _apply_section(), EngineConfig, InteractiveConfig, load_engine_config(), PipelineConfig, Unified engine configuration loader. 统一引擎配置加载器。 Loads ``config engine_config, Load engine configuration from YAML. Args config_path Explici, Pipeline-level defaults for LLM calls. (+18 more)

### Community 34 - "C: Users"
Cohesion: 0.09
Nodes (28): _aggregate_confidence(), compute_mediation_range(), _decimal_val(), _get_attr_or_key(), MediationRange, 调解区间计算 — 基于金额报告和裁判路径树估算和解建议金额范围。 Mediation range calculator — estimates settlem, Extract and average confidence intervals from decision tree paths. Return, Get value from object attribute or dict key. (+20 more)

### Community 35 - "C: Users"
Cohesion: 0.05
Nodes (12): PII 脱敏模块测试 Tests for PII redaction module., 包含身份证号的文本经脱敏后替换为 。, 包含手机号的文本经脱敏后替换为 1XX XXXX。, 同一文本中包含多种 PII 类型全部脱敏。, 脱敏正则匹配异常时返回原文（不破坏报告生成）。 We mock the redact function to simulate a reg, TestBuildNameMap, TestDisclaimerTemplates, TestRedactBankCard (+4 more)

### Community 36 - "C: Users"
Cohesion: 0.06
Nodes (33): _make_golden_run(), Phase 0b N=3 consistency checks for multi-case-type acceptance. Tests that, Build a synthetic but structurally realistic pipeline run result. Args, Write realistic pipeline artifacts to disk for extract_run_artifacts() to parse., With 3 identical runs, all metrics should be at maximum., With 2 3 identical + 1 slightly different, consistency = 0.75 threshold., Missing citations should cause citation_rate to drop below 1.0., Pipeline failures should reduce n_success and potentially fail acceptance. (+25 more)

### Community 37 - "C: Users"
Cohesion: 0.06
Nodes (14): _assert_registry_has_case_types(), 多案型 prompt 注册表单元测试。 Unit tests for multi-case-type prompt registry registration, evidence_weight_scorer prompt 注册表测试。, admissibility_evaluator prompt 注册表测试。, adversarial prompt 注册表测试。, PromptProfile 枚举包含新案型。, issue_extractor prompt 注册表测试。, evidence_indexer prompt 注册表测试。 (+6 more)

### Community 38 - "C: Users"
Cohesion: 0.06
Nodes (16): json_utils 单元测试 Unit tests for json_utils. 覆盖： - _repair_json_string 关键场景, 含数组的 JSON 被截断时能恢复已有内容。, 完整 JSON 经截断恢复路径仍能正确解析。, 完全无 JSON 内容时应抛 ValueError。, 从 markdown 代码块中提取 JSON 对象。, _extract_json_array 基本路径。, _repair_json_string 的关键场景。, 纯净的 JSON 字符串经过修复后应保持不变。 (+8 more)

### Community 39 - "C: Users"
Cohesion: 0.07
Nodes (17): _minimal_issue(), P0.1 数据模型单元测试 — 新增枚举和 Issue 扩展字段。, 旧数据（无 P0.1 字段）可正常反序列化。, Unit 22 Phase C 回归：list[str] 字段对 str-Enum 的强制转换。 Phase C 把 ``Issue.impact, 直接赋值 ImpactTarget 实例 → 字段实际存的是 str（不是 enum）。, 混合 enum 和 str 输入 → 全部存为 str。, str-Enum 协议保证：coerced str 与原始 enum 用 == 比较相等。, 关键：coerced str 必须能与 ranker 的 frozenset[str] 词汇做 in 操作。 如果 Pydantic 把它 (+9 more)

### Community 40 - "C: Users"
Cohesion: 0.09
Nodes (11): _base_output(), _make_risk_flag(), P2.10 数据模型单元测试 — RiskImpactObject RiskFlag AgentOutput migration, v1.5 str risk_flags no longer accepted, must raise ValidationError., v1.5 mixed list with str elements must also be rejected., Pydantic should coerce dict - RiskFlag., impact_objects must not be empty when impact_objects_scored=True., Legacy-migrated RiskFlag may have empty impact_objects. (+3 more)

### Community 41 - "C: Users"
Cohesion: 0.08
Nodes (26): analyzed_case_id(), client(), client_with_users(), created_case_id(), created_case_id_with_users(), _get_jwt(), jwt_for_admin(), jwt_for_junior() (+18 more)

### Community 42 - "C: Users"
Cohesion: 0.19
Nodes (30): _cross_exam_json(), _defense_json(), _make_engine(), _make_evidence(), _make_evidence_index(), _make_input(), _make_issue(), _make_issue_tree() (+22 more)

### Community 43 - "C: Users"
Cohesion: 0.11
Nodes (4): _drain(), TestCLIProgressReporter, TestJSONProgressReporter, TestSSEProgressReporter

### Community 44 - "C: Users"
Cohesion: 0.09
Nodes (6): P1.8 数据模型单元测试 — ClaimAmendmentSuggestion ClaimAbandonSuggestion TrialExplan, evidence_ids 可为空列表（某些争点无直接证据绑定）。, TestActionRecommendation, TestClaimAbandonSuggestion, TestClaimAmendmentSuggestion, TestTrialExplanationPriority

### Community 45 - "C: Users"
Cohesion: 0.07
Nodes (5): Tests for the ReportFixer — format fixes applied before lint., TestApplyAll, TestFixCjkPunctuation, TestFixDuplicateHeadings, TestFixTableColumnMismatch

### Community 46 - "C: Users"
Cohesion: 0.16
Nodes (27): _aggregate_results(), _best_match(), _best_match_llm(), _bigram_jaccard(), build_raw_materials(), build_synthetic_claims(), _char_jaccard(), _collect_candidate_pairs() (+19 more)

### Community 47 - "C: Users"
Cohesion: 0.07
Nodes (11): Tests for Phase 3 human review workflow endpoints., approved is a terminal state — no further reviews allowed., rejected is a terminal state., Cannot approve when review_status is still 'none'., action=none is not a valid submission action., GET api cases {case_id} reviews, CaseListEntry should include review_status., POST api cases {case_id} reviews (+3 more)

### Community 48 - "C: Users"
Cohesion: 0.09
Nodes (26): build_cross_exam_user_prompt(), build_user_prompt(), _escape_xml(), format_input_block(), format_issue_tree_block(), format_materials_block(), format_parties_block(), 房屋买卖合同纠纷（Real Estate）案件类型的场景推演 LLM 提示模板。 LLM prompt templates for real estate s (+18 more)

### Community 49 - "C: Users"
Cohesion: 0.15
Nodes (26): _make_labor_dispute_report(), test_all_major_sections_substantive(), test_amount_calculation_has_labor_fields(), test_amount_calculation_section_present(), test_amount_section_absent_when_no_amount_data(), test_amount_uses_labor_formula_not_loan_formula(), test_blocking_conditions_present(), test_both_perspectives_present() (+18 more)

### Community 50 - "C: Users"
Cohesion: 0.15
Nodes (26): _make_real_estate_report(), test_all_major_sections_substantive(), test_amount_calculation_has_real_estate_fields(), test_amount_calculation_section_present(), test_amount_section_absent_when_no_amount_data(), test_amount_uses_real_estate_terms_not_other_case_types(), test_blocking_conditions_present(), test_both_perspectives_present() (+18 more)

### Community 51 - "C: Users"
Cohesion: 0.1
Nodes (25): build_cross_exam_user_prompt(), build_user_prompt(), _escape_xml(), format_input_block(), format_issue_tree_block(), format_materials_block(), format_parties_block(), 劳动争议（Labor Dispute）案件类型的场景推演 LLM 提示模板。 LLM prompt templates for labor dispute c (+17 more)

### Community 52 - "C: Users"
Cohesion: 0.1
Nodes (13): _generate_md(), Phase 3d multi-case-type integration tests. Validates 1. All 3 case type, Case-type-specific terms must not leak into other case types., Golden artifacts must exist and pass render contract., Each golden artifact title must reflect its own case type., Generate MD report content using write_v3_report_md., Every case type must pass render contract at the 0.20 final gate., test_fallback_ratio_at_0_20() (+5 more)

### Community 53 - "C: Users"
Cohesion: 0.11
Nodes (25): _check_path_explainability(), _compute_citation_rate(), _compute_issue_tree_stability(), compute_metrics(), _default_pipeline_runner(), _extract_decision_tree_artifacts(), extract_run_artifacts(), load_and_validate_yaml() (+17 more)

### Community 54 - "C: Users"
Cohesion: 0.08
Nodes (13): Tests for Phase 5 export endpoints (JSON, markdown, bulk ZIP)., GET api cases {case_id} export format=json, conlist(str, max_length=50) should reject 50 case_ids., Export operations should emit 'exported' events., Created (unanalyzed) case should still export — analysis_data will be null., GET api cases {case_id} export format=markdown, POST api cases export bulk, Nonexistent case_ids are silently skipped. (+5 more)

### Community 55 - "C: Users"
Cohesion: 0.08
Nodes (2): _make_response(), mock_llm()

### Community 56 - "C: Users"
Cohesion: 0.16
Nodes (24): _make_civil_loan_report(), test_all_major_sections_substantive(), test_amount_calculation_has_loan_fields(), test_amount_calculation_section_present(), test_amount_section_absent_when_no_amount_report(), test_blocking_conditions_present(), test_both_perspectives_present(), test_civil_loan_fallback_ratio_below_threshold() (+16 more)

### Community 57 - "C: Users"
Cohesion: 0.09
Nodes (5): _minimal_report(), test_fallback_gate_blocks_ratio_above_0_20(), test_fallback_gate_passes_ratio_below_0_20(), test_write_v3_report_md_rejects_high_fallback_ratio(), test_write_v3_report_md_rejects_polluted_render()

### Community 58 - "C: Users"
Cohesion: 0.11
Nodes (13): Pytest tests for the DOCX v3 report generator (generate_docx_v3_report)., Minimal report dict generates a .docx file with non-zero size., Layer 1 renders the main section heading and timeline sub-heading., When winning_move is populated, '胜负手' heading appears., Core 6-field evidence card (ev-001) renders with '2.4 证据卡片' heading and, Supporting card (ev-002, no q5 q6) renders a 4-row table only., Unified electronic evidence strategy heading renders when populated., Layer 4 glossary section heading appears when glossary_md is set. (+5 more)

### Community 59 - "C: Users"
Cohesion: 0.11
Nodes (8): _mock_llm_client(), test_action_recommender_init(), test_admissibility_evaluator_init(), test_attack_chain_optimizer_init(), test_decision_path_tree_generator_init(), test_evidence_indexer_init(), test_issue_extractor_init(), test_issue_impact_ranker_init()

### Community 60 - "C: Users"
Cohesion: 0.14
Nodes (11): _make_llm_response(), MockLLMClient, test_analyze_returns_output_and_conflicts(), test_empty_conflicts_when_no_conflict_in_response(), test_evidence_citations_from_arguments(), test_evidence_manager_rejects_empty_citations(), test_generate_claim_returns_agent_output(), test_generate_claim_returns_defendant_role() (+3 more)

### Community 61 - "C: Users"
Cohesion: 0.1
Nodes (19): check_acceptance_criteria_version(), check_acceptance_json_parseable(), check_bulwark_tasks_exist(), check_case_object_model_complete(), check_current_plan_targets_v05(), check_hard_fail_defined(), check_hard_fail_json_conditions(), _fail() (+11 more)

### Community 62 - "C: Users"
Cohesion: 0.13
Nodes (13): _make_all_evidence(), _make_evidence(), AccessController v1.5 ProcedureState 驱动访问控制测试。, judge_questions 阶段只看到 admitted_for_discussion。, 即使是 plaintiff，在 judge_questions 阶段也只看 admitted。, evidence_challenge 阶段看到 submitted + own private。, judge 在 evidence_challenge 阶段看不到任何东西 （judge 本身只有 admitted_record 域权限）。, procedure_state=None 时行为与 v1 完全一致。 (+5 more)

### Community 63 - "C: Users"
Cohesion: 0.16
Nodes (6): make_suggestion(), AlternativeClaimSuggestion 模型约束测试（P2.11）。 验证 Pydantic 强制的合约： - instability_i, 构造合法的最小 AlternativeClaimSuggestion。, instability_issue_ids 为空列表时必须抛出 ValidationError（零容忍）。, instability_evidence_ids 允许为空列表。, TestAlternativeClaimSuggestionModel

### Community 64 - "C: Users"
Cohesion: 0.35
Nodes (19): _make_admitted_evidence(), _make_agent(), _make_issue(), _make_issue_tree(), _make_llm_response(), test_blocking_conditions_in_prompt(), test_case_id_and_run_id_set(), test_evidence_gaps_in_prompt() (+11 more)

### Community 65 - "C: Users"
Cohesion: 0.19
Nodes (19): compute_fallback_ratio(), _extract_sections(), _find_cjk_punctuation_mix(), _find_duplicate_headings(), _find_empty_major_sections(), _find_excessive_fallback(), _find_forbidden_tokens(), _find_orphan_citations() (+11 more)

### Community 66 - "C: Users"
Cohesion: 0.13
Nodes (19): build_humanize_context(), _chinese_numeral(), format_tag(), humanize_field_value(), humanize_id(), humanize_text(), 标注系统 Tag system for V3 reports. 全文强制标注：「事实」「推断」「假设」「观点」「建议」 Every section, Convert internal IDs to human-readable form. Args raw_id The r (+11 more)

### Community 67 - "C: Users"
Cohesion: 0.19
Nodes (17): _build_claims(), _build_defenses(), _build_financials(), _build_gap_descriptors_from_adversarial(), _build_materials(), _derive_evidence_gaps(), _ensure_report_docx_alias(), _load_case() (+9 more)

### Community 68 - "C: Users"
Cohesion: 0.16
Nodes (18): build_search_payload(), discover_response_format(), extract_data_list(), extract_keywords(), fetch_page(), main(), normalize_case(), Navigate to login and wait for the user to complete authentication. (+10 more)

### Community 69 - "C: Users"
Cohesion: 0.19
Nodes (14): _seed_index(), test_query_combined_filters(), test_query_filter_by_case_type(), test_query_filter_by_date_range(), test_query_filter_by_status(), test_query_page_beyond_total(), test_query_pagination(), test_query_sort_created_at_asc() (+6 more)

### Community 70 - "C: Users"
Cohesion: 0.18
Nodes (3): _setup_analyzed_case(), TestGetCaseScenario, TestPostCaseScenario

### Community 71 - "C: Users"
Cohesion: 0.15
Nodes (10): ConsistencyChecker, ConsistencyChecker — 输出前一致性校验模块（v7）。 Consistency Checker — pre-output consisten, 同一 section 内不得混用中立评估和一方策略建议。 规则： - perspective=neutral 的 sec, 若整体态势偏被告、且最可能路径对被告有利， 则原告侧的建议（如 strategic_headline）不应呈现 全额稳拿 风格。, 证据可采性不明（uncertain weak excluded）时， 依赖该证据的争点不得排在 outcome_impact=high 的第一, 被强反证（dispute_ratio 0.6）或孤证的证据， 不应仍排在 top tier 争点的核心证据中。 修订, 行动建议必须与当前立场和路径判断一致。 修订清单一-6：系统判断原告整体劣势时，不输出 全额稳拿 风格的动作建议。, 输出前一致性校验器（v7）。 纯规则层，不持有外部状态，可安全复用同一实例。 使用方式 Usage chec (+2 more)

### Community 72 - "C: Users"
Cohesion: 0.13
Nodes (6): Unit 22 Phase B Party.litigation_history is now a neutral dict[str, Any]., TestAmountConsistencyCheckExtensions, TestContractValidity, TestInterestRecalculation, TestLitigationHistory, TestPartyLitigationHistory

### Community 73 - "C: Users"
Cohesion: 0.2
Nodes (5): P1.6 数据模型单元测试 — 新增枚举和 Issue 扩展字段。, Issue.issue_category 扩展字段测试。, issue_category 与 issue_type 并列存在，互不影响。, TestIssueCategory, TestIssueIssueCategoryField

### Community 74 - "C: Users"
Cohesion: 0.15
Nodes (11): Unit 8 Scenario API 端点测试。 Tests for POST api scenarios run and GET api scena, GET scenarios {scenario_id} — scenario 存在 → 200 + ScenarioDiff。, GET scenarios {scenario_id} — scenario 不存在 → 404。, run_id 不存在 → 404 + 响应 detail 包含 run_id。, change_set 缺必填字段（target_object_type, field_path）→ 422。, 有效 change_set → 200 + ScenarioDiff JSON，diff_entries 非空。, test_get_scenario_found_returns_200(), test_get_scenario_not_found_returns_404() (+3 more)

### Community 75 - "C: Users"
Cohesion: 0.22
Nodes (12): _build_name_map(), PII 脱敏模块 PII Redaction module. 在报告输出层统一脱敏，不在中间层做。 Applied at the report out, 对文本执行全量 PII 脱敏。 Apply all PII redaction to text. Safe to call on any text, 从当事人姓名列表构建 姓名→角色代号 映射。 Build name → role code mapping from party name lis, 将手机号替换为 `1XX XXXX` 格式（保留前3后4）。, 将银行卡号替换为 `XXXX XXXX` 格式（保留前4后4）。, 将白名单中的姓名替换为角色代号。 按姓名长度降序替换，避免短名被长名子串误匹配。, redact_bank_card() (+4 more)

### Community 76 - "Community 76"
Cohesion: 0.15
Nodes (0): 

### Community 77 - "C: Users"
Cohesion: 0.38
Nodes (8): _make_evidence_index(), _make_fake_result(), _make_issue_tree(), _make_material(), test_analyze_endpoint_is_single_flight(), test_extract_endpoint_is_single_flight(), test_reports_and_artifacts_survive_workspace_recovery(), test_scenario_service_reads_case_type_from_baseline_metadata()

### Community 78 - "C: Users"
Cohesion: 0.24
Nodes (8): _add_bullet(), _add_run(), _add_styled_para(), Set font for all cells in a table., Add a formatted run to a paragraph., Add a single-run paragraph with consistent styling., Add a bullet point paragraph., _set_table_font()

### Community 79 - "C: Users"
Cohesion: 0.33
Nodes (9): find_docx(), find_latest_output_dir(), insert_similar_cases_section(), load_index(), main(), Insert a 类案检索参考 section before the last paragraph of the DOCX., Score a case entry by keyword overlap — same logic as LocalCaseSearcher., score_case() (+1 more)

### Community 80 - "C: Users"
Cohesion: 0.22
Nodes (7): Unit tests for Bearer Token authentication middleware. Covers 401 when key con, 当 API_SECRET_KEY 已配置时，无 token 请求应返回 401。, 当 API_SECRET_KEY 已配置时，携带正确 Bearer token 应通过认证。, 未配置 API_SECRET_KEY 时，所有请求应开放访问（不强制认证）。, test_no_auth_when_key_not_configured(), test_protected_endpoint_accepts_valid_token(), test_protected_endpoint_returns_401_without_token()

### Community 81 - "C: Users"
Cohesion: 0.32
Nodes (7): _extract_json_array(), _extract_json_object(), 共享 JSON 解析工具 Shared JSON parsing utilities. 供四个引擎共用，避免重复实现。 Shared across, 从 LLM 响应中提取 JSON 数组。 Extract a JSON array from LLM response text. 依次, 简单修复 LLM 生成的 JSON 中的常见问题。 Simple repair for common LLM JSON formatting issu, 从 LLM 响应中提取 JSON 对象。 Extract a JSON object from LLM response text. 依, _repair_json_string()

### Community 82 - "C: Users"
Cohesion: 0.25
Nodes (1): test_event_fields_roundtrip()

### Community 83 - "C: Users"
Cohesion: 0.48
Nodes (6): main(), _parse_args(), _print_summary(), 打印提取摘要到 stderr。Print extraction summary to stderr., _read_input(), _run()

### Community 84 - "C: Users"
Cohesion: 0.33
Nodes (5): build_extraction_prompt(), format_documents(), Generic case extraction prompt — works for all case types. 通用案件提取 prompt — 适用于所, Build the extraction prompt with document text safely inserted. Uses plac, Format document texts into XML blocks for the extraction prompt. Args

### Community 85 - "C: Users"
Cohesion: 0.6
Nodes (5): main(), _output_dir(), _run_rounds(), _write_json(), _write_md()

### Community 86 - "C: Users"
Cohesion: 0.6
Nodes (5): main(), _output_dir(), _run_rounds(), _write_json(), _write_md()

### Community 87 - "C: Users"
Cohesion: 0.5
Nodes (3): call_llm_with_retry(), LLM 调用工具 — 统一的重试逻辑（指数退避 + jitter）。 LLM call utilities — centralized retry logic, LLM 调用（带指数退避重试）。 Call LLM with exponential backoff retry. 仅在 LLM 网络

### Community 88 - "C: Users"
Cohesion: 0.83
Nodes (3): main(), _print_result(), _run_checks()

### Community 89 - "C: Users"
Cohesion: 0.67
Nodes (1): 法官追问 prompt 模板。 Judge questioning prompt templates.

### Community 90 - "Community 90"
Cohesion: 0.67
Nodes (0): 

### Community 91 - "C: Users"
Cohesion: 1.0
Nodes (2): _build_parser(), _main()

### Community 92 - "C: Users"
Cohesion: 1.0
Nodes (2): _read_docx_text(), test_run_case_resume_regenerates_probability_free_reports()

### Community 93 - "C: Users"
Cohesion: 1.0
Nodes (1): DOCX style constants shared across report-generation modules. Centralizes col

### Community 94 - "C: Users"
Cohesion: 1.0
Nodes (1): 免责声明模板 Disclaimer templates for report output. 固定中文文本，用于 Markdown 报告首行和 DOCX

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (0): 

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (0): 

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (0): 

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (0): 

### Community 99 - "C: Users"
Cohesion: 1.0
Nodes (1): Fields the LLM could not extract — user should fill manually.

### Community 100 - "C: Users"
Cohesion: 1.0
Nodes (1): 无 error 则校验通过 Validation passes if no errors.

### Community 101 - "C: Users"
Cohesion: 1.0
Nodes (1): format_input_block 可以用空输入正常运行，不应抛出异常。

### Community 102 - "C: Users"
Cohesion: 1.0
Nodes (1): 计算引用完整性得分（0.0–1.0）。 Compute citation completeness score (0.0–1.0).

### Community 103 - "C: Users"
Cohesion: 1.0
Nodes (1): True when the checkpoint contains v3 report artifacts.

### Community 104 - "C: Users"
Cohesion: 1.0
Nodes (1): Return the global model override, if set.

### Community 105 - "C: Users"
Cohesion: 1.0
Nodes (1): 从 YAML 配置文件加载。 Load from a YAML config file. Expected YAML s

### Community 106 - "C: Users"
Cohesion: 1.0
Nodes (1): Parse a config dict into a ModelSelector.

### Community 107 - "C: Users"
Cohesion: 1.0
Nodes (1): Called when a pipeline step begins execution.

### Community 108 - "C: Users"
Cohesion: 1.0
Nodes (1): Called when a pipeline step finishes successfully.

### Community 109 - "C: Users"
Cohesion: 1.0
Nodes (1): Called when a pipeline step fails.

### Community 110 - "C: Users"
Cohesion: 1.0
Nodes (1): 每个 simulation_run 分析模块的 PROMPT_REGISTRY 必须包含全部 3 个案型。

### Community 111 - "C: Users"
Cohesion: 1.0
Nodes (1): 每个案型在 PROMPT_REGISTRY 中的注册值不得为 None 或空。

### Community 112 - "C: Users"
Cohesion: 1.0
Nodes (1): 2 identical + 1 reordered → consistency = 2 3 ≈ 0.667 (below threshold).

### Community 113 - "C: Users"
Cohesion: 1.0
Nodes (1): 3 3 identical → consistency = 1.0 (above threshold).

### Community 114 - "C: Users"
Cohesion: 1.0
Nodes (1): 2 successful + 1 failed → n_success=2 MIN_VALID_RUNS=3 → fails.

### Community 115 - "C: Users"
Cohesion: 1.0
Nodes (1): N=3 golden artifacts should pass full acceptance when extracted from disk.

### Community 116 - "C: Users"
Cohesion: 1.0
Nodes (1): N=3 reads of the same golden artifacts should pass acceptance.

## Knowledge Gaps
- **618 isolated node(s):** `案件内存索引 — 启动时扫描磁盘重建，运行时同步更新。 In-memory case index — rebuilt from disk on startup`, `In-memory case index. Rebuilt on startup via scan_from_disk(); kept curre`, `Walk workspaces_dir case_meta.json and rebuild the index. Returns t`, `Filter, sort, and paginate the index. Returns (page_entries, total_ma`, `Parse an ISO8601 string, normalizing 'Z' to '+00 00'.` (+613 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `C: Users`** (2 nodes): `docx_styles.py`, `DOCX style constants shared across report-generation modules. Centralizes col`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (2 nodes): `disclaimer_templates.py`, `免责声明模板 Disclaimer templates for report output. 固定中文文本，用于 Markdown 报告首行和 DOCX`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (2 nodes): `test_consistency_checker.py`, `test_recommendation_failure_message_is_probability_free()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (2 nodes): `test_display_resolver.py`, `test_resolve_path_omits_probability_suffix()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (2 nodes): `extract_case.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (2 nodes): `regen_docx.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Fields the LLM could not extract — user should fill manually.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `无 error 则校验通过 Validation passes if no errors.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `format_input_block 可以用空输入正常运行，不应抛出异常。`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `计算引用完整性得分（0.0–1.0）。 Compute citation completeness score (0.0–1.0).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `True when the checkpoint contains v3 report artifacts.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Return the global model override, if set.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `从 YAML 配置文件加载。 Load from a YAML config file. Expected YAML s`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Parse a config dict into a ModelSelector.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Called when a pipeline step begins execution.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Called when a pipeline step finishes successfully.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Called when a pipeline step fails.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `每个 simulation_run 分析模块的 PROMPT_REGISTRY 必须包含全部 3 个案型。`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `每个案型在 PROMPT_REGISTRY 中的注册值不得为 None 或空。`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `2 identical + 1 reordered → consistency = 2 3 ≈ 0.667 (below threshold).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `3 3 identical → consistency = 1.0 (above threshold).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `2 successful + 1 failed → n_success=2 MIN_VALID_RUNS=3 → fails.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `N=3 golden artifacts should pass full acceptance when extracted from disk.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `N=3 reads of the same golden artifacts should pass acceptance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.` connect `C: Users` to `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`, `C: Users`?**
  _High betweenness centrality (0.185) - this node is a cross-community bridge._
- **Why does `WorkspaceManager` connect `C: Users` to `C: Users`, `C: Users`, `C: Users`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `ExecutiveSummarizerInput` connect `C: Users` to `C: Users`, `C: Users`, `C: Users`, `C: Users`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 266 inferred relationships involving `SectionTag` (e.g. with `场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.` and `证据作战矩阵生成器 Evidence Battle Matrix Generator. V3.1 双层证据卡： - EvidenceBasicCard`) actually correct?**
  _`SectionTag` has 266 INFERRED edges - model-reasoned connections that need verification._
- **Are the 223 inferred relationships involving `EvidenceBasicCard` (e.g. with `场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.` and `证据作战矩阵生成器 Evidence Battle Matrix Generator. V3.1 双层证据卡： - EvidenceBasicCard`) actually correct?**
  _`EvidenceBasicCard` has 223 INFERRED edges - model-reasoned connections that need verification._
- **Are the 205 inferred relationships involving `Layer3Perspective` (e.g. with `场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.` and `Layer 3 角色化输出层 Role-based Output Layer (V3.1). --perspective 驱动的 纯动作方案 输出层`) actually correct?**
  _`Layer3Perspective` has 205 INFERRED edges - model-reasoned connections that need verification._
- **Are the 202 inferred relationships involving `EvidencePriority` (e.g. with `场景推演 Prompt 模板注册表 Scenario simulation prompt template registry.` and `证据作战矩阵生成器 Evidence Battle Matrix Generator. V3.1 双层证据卡： - EvidenceBasicCard`) actually correct?**
  _`EvidencePriority` has 202 INFERRED edges - model-reasoned connections that need verification._