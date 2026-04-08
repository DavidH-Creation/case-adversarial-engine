---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\simulation_run\issue_category_classifier\tests\test_classifier.py"
type: "code"
community: "C: Users"
location: "L47"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/C:_Users
---

# MockLLMClient

## Connections
- [[.__init__()_73]] - `method` [EXTRACTED]
- [[.create_message()_19]] - `method` [EXTRACTED]
- [[IssueCategoryClassificationResult]] - `uses` [INFERRED]
- [[IssueCategoryClassifier]] - `uses` [INFERRED]
- [[IssueCategoryClassifierInput]] - `uses` [INFERRED]
- [[test_all_four_categories_accepted()]] - `calls` [INFERRED]
- [[test_calculation_issue_with_empty_claim_entry_ids_clears_field()]] - `calls` [INFERRED]
- [[test_calculation_issue_with_valid_claim_entry_passes()]] - `calls` [INFERRED]
- [[test_calculation_issue_without_valid_claim_entry_clears_field()]] - `calls` [INFERRED]
- [[test_category_without_basis_clears_field()]] - `calls` [INFERRED]
- [[test_claim_entries_included_in_prompt()]] - `calls` [INFERRED]
- [[test_classifier.py]] - `contains` [EXTRACTED]
- [[test_empty_issue_tree_returns_immediately()]] - `calls` [INFERRED]
- [[test_invalid_category_clears_field()]] - `calls` [INFERRED]
- [[test_issue_type_preserved_after_classification()]] - `calls` [INFERRED]
- [[test_llm_called_once()_1]] - `calls` [INFERRED]
- [[test_llm_failure_returns_original_tree_all_unclassified()]] - `calls` [INFERRED]
- [[test_llm_missing_issue_goes_to_unclassified()]] - `calls` [INFERRED]
- [[test_llm_retry_on_transient_failure()]] - `calls` [INFERRED]
- [[test_result_created_at_is_set()]] - `calls` [INFERRED]
- [[test_unknown_issue_id_in_llm_output_is_ignored()]] - `calls` [INFERRED]
- [[test_unsupported_case_type_raises()_5]] - `calls` [INFERRED]
- [[test_valid_fact_issue_classification()]] - `calls` [INFERRED]
- [[返回预定义 JSON 响应的 mock LLM 客户端。 Mock LLM client that returns predefined JSON r_3]] - `rationale_for` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/C:_Users