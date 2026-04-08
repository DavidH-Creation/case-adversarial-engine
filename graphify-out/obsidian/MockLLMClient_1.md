---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\case_structuring\issue_extractor\tests\test_extractor.py"
type: "code"
community: "C: Users"
location: "L40"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# MockLLMClient

## Connections
- [[.__init__()_18]] - `method` [EXTRACTED]
- [[.create_message()_4]] - `method` [EXTRACTED]
- [[CaseExtractionResult]] - `uses` [INFERRED]
- [[CaseExtractor]] - `uses` [INFERRED]
- [[ExtractedCase]] - `uses` [INFERRED]
- [[IssueExtractor]] - `uses` [INFERRED]
- [[LLMExtractedClaim]] - `uses` [INFERRED]
- [[LLMExtractedDefense]] - `uses` [INFERRED]
- [[LLMExtractedFinancials]] - `uses` [INFERRED]
- [[LLMExtractedLoan]] - `uses` [INFERRED]
- [[LLMExtractedMaterial]] - `uses` [INFERRED]
- [[LLMExtractedParty]] - `uses` [INFERRED]
- [[LLMExtractedRepayment]] - `uses` [INFERRED]
- [[LLMExtractedSummaryRow]] - `uses` [INFERRED]
- [[LLMExtractionOutput]] - `uses` [INFERRED]
- [[Mock LLM client returning predefined JSON responses.]] - `rationale_for` [EXTRACTED]
- [[ValidationReport]] - `uses` [INFERRED]
- [[test_all_claims_mapped()]] - `calls` [INFERRED]
- [[test_all_defenses_mapped()]] - `calls` [INFERRED]
- [[test_burden_ids_linked_to_root_issues()]] - `calls` [INFERRED]
- [[test_civil_loan_extraction_produces_valid_case()]] - `calls` [INFERRED]
- [[test_complete_case_passes_validation()]] - `calls` [INFERRED]
- [[test_custom_case_id()]] - `calls` [INFERRED]
- [[test_duplicate_claim_id_raises()]] - `calls` [INFERRED]
- [[test_duplicate_defense_id_raises()]] - `calls` [INFERRED]
- [[test_empty_claims_raises_value_error()]] - `calls` [INFERRED]
- [[test_empty_defenses()]] - `calls` [INFERRED]
- [[test_empty_input_raises_value_error()]] - `calls` [INFERRED]
- [[test_existing_burden_not_duplicated()]] - `calls` [INFERRED]
- [[test_extract_ambiguous_amounts()]] - `calls` [INFERRED]
- [[test_extract_empty_input_raises()]] - `calls` [INFERRED]
- [[test_extract_full_parties_and_amount()]] - `calls` [INFERRED]
- [[test_extract_missing_defendant_marked_unknown()]] - `calls` [INFERRED]
- [[test_extract_multiple_defendants()]] - `calls` [INFERRED]
- [[test_extract_retries_on_llm_failure()]] - `calls` [INFERRED]
- [[test_extract_returns_issue_tree()]] - `calls` [INFERRED]
- [[test_extract_three_evidence_items()]] - `calls` [INFERRED]
- [[test_extraction_metadata_counts()]] - `calls` [INFERRED]
- [[test_extraction_survives_braces_in_input()]] - `calls` [INFERRED]
- [[test_extractor.py]] - `contains` [EXTRACTED]
- [[test_fact_propositions_get_ids()]] - `calls` [INFERRED]
- [[test_fallback_burden_has_required_fields()]] - `calls` [INFERRED]
- [[test_generated_yaml_is_valid()]] - `calls` [INFERRED]
- [[test_initial_issue_status_is_open()]] - `calls` [INFERRED]
- [[test_issue_ids_use_case_slug()]] - `calls` [INFERRED]
- [[test_labor_dispute_extraction_no_financials()]] - `calls` [INFERRED]
- [[test_llm_receives_system_and_user_prompts()]] - `calls` [INFERRED]
- [[test_llm_retry_exhausted_raises_runtime_error()]] - `calls` [INFERRED]
- [[test_llm_retry_on_failure()]] - `calls` [INFERRED]
- [[test_llm_retry_succeeds_after_failures()]] - `calls` [INFERRED]
- [[test_materials_grouped_by_submitter()]] - `calls` [INFERRED]
- [[test_missing_financials_for_loan_case()]] - `calls` [INFERRED]
- [[test_multi_file_input()]] - `calls` [INFERRED]
- [[test_parent_issue_id_resolved()]] - `calls` [INFERRED]
- [[test_root_issue_gets_fallback_burden_when_llm_omits()]] - `calls` [INFERRED]
- [[test_to_yaml_structure()]] - `calls` [INFERRED]
- [[test_unknown_evidence_ids_filtered_from_fact_propositions()]] - `calls` [INFERRED]
- [[test_unknown_evidence_ids_filtered_from_issue()]] - `calls` [INFERRED]
- [[test_unknown_prompt_raises_value_error()]] - `calls` [INFERRED]
- [[test_unsupported_case_type_raises()]] - `calls` [INFERRED]
- [[test_yaml_has_header_comments()]] - `calls` [INFERRED]
- [[test_yaml_passes_load_case_validation()]] - `calls` [INFERRED]
- [[test_yaml_round_trip_preserves_structure()]] - `calls` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client returning predefined JSON resp]] - `rationale_for` [EXTRACTED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client that returns predefined JSON r]] - `rationale_for` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/C:_Users