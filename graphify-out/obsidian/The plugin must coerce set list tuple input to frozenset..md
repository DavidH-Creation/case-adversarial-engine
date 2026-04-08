---
source_file: "C:\Users\david\dev\case-adversarial-engine\engines\shared\tests\test_case_type_plugin.py"
type: "rationale"
community: "C: Users"
location: "L176"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/C:_Users
---

# The plugin must coerce set list tuple input to frozenset.

## Connections
- [[.test_dict_based_accepts_set_or_list_and_returns_frozenset()]] - `rationale_for` [EXTRACTED]
- [[CaseTypePlugin]] - `uses` [INFERRED]
- [[RegistryPlugin]] - `uses` [INFERRED]
- [[UnsupportedCaseTypeError]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/C:_Users