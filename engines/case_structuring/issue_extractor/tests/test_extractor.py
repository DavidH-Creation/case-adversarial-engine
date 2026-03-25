"""
IssueExtractor 单元测试。
IssueExtractor unit tests.

使用 mock LLM 客户端验证：
Validates using a mock LLM client:
- 输出符合 IssueTree 结构 / Output conforms to IssueTree structure
- issue_id 自动生成且含 case_slug / issue_ids auto-generated with case_slug
- 争点层级（parent_issue_id）正确解析 / Issue hierarchy resolved correctly
- Claim/Defense 完整映射 / Complete Claim/Defense mapping
- 事实命题分配 proposition_id / FactPropositions assigned proposition_ids
- 输入校验（claims 为空、claim_id 重复）/ Input validation
- LLM 重试逻辑 / LLM retry logic
- JSON 解析（含 markdown 代码块）/ JSON parsing including markdown code blocks
"""

from __future__ import annotations

import json

import pytest

from engines.case_structuring.issue_extractor.schemas import (
    IssueStatus,
    IssueTree,
    IssueType,
)
from engines.case_structuring.issue_extractor.extractor import (
    IssueExtractor,
    _extract_json_object,
    _resolve_issue_type,
)


# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。
    Mock LLM client that returns predefined JSON responses.

    可配置前 N 次调用失败，用于测试重试逻辑。
    Configurable to fail the first N calls for testing retry logic.
    """

    def __init__(self, response: str, fail_times: int = 0) -> None:
        self._response = response
        self._fail_times = fail_times
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        if self._fail_times > 0 and self.call_count <= self._fail_times:
            raise RuntimeError(f"Simulated LLM failure on attempt {self.call_count}")
        return self._response


# ---------------------------------------------------------------------------
# 测试数据 / Test data
# ---------------------------------------------------------------------------

MOCK_LLM_RESPONSE = json.dumps(
    {
        "issues": [
            {
                "tmp_id": "issue-tmp-001",
                "title": "借贷关系成立",
                "issue_type": "factual",
                "parent_tmp_id": None,
                "related_claim_ids": ["claim-civil-loan-001-01", "claim-civil-loan-001-02"],
                "related_defense_ids": [],
                "evidence_ids": ["evidence-civil-loan-001-01"],
                "fact_propositions": [
                    {
                        "text": "双方存在合法有效的借贷合意",
                        "status": "supported",
                        "linked_evidence_ids": ["evidence-civil-loan-001-01"],
                    }
                ],
            },
            {
                "tmp_id": "issue-tmp-002",
                "title": "还款事实",
                "issue_type": "factual",
                "parent_tmp_id": "issue-tmp-001",
                "related_claim_ids": ["claim-civil-loan-001-01"],
                "related_defense_ids": ["defense-civil-loan-001-01"],
                "evidence_ids": ["evidence-civil-loan-001-02", "evidence-civil-loan-001-03"],
                "fact_propositions": [
                    {
                        "text": "被告已归还部分借款本金",
                        "status": "disputed",
                        "linked_evidence_ids": ["evidence-civil-loan-001-03"],
                    }
                ],
            },
        ],
        "burdens": [
            {
                "issue_tmp_id": "issue-tmp-001",
                "bearer_party_id": "party-civil-loan-001-01",
                "description": "原告应证明借贷关系成立，包括借贷合意和款项交付",
                "proof_standard": "高度盖然性",
                "legal_basis": "《最高院民间借贷司法解释》第二条",
            }
        ],
        "claim_issue_mapping": [
            {
                "claim_id": "claim-civil-loan-001-01",
                "issue_tmp_ids": ["issue-tmp-001", "issue-tmp-002"],
            },
            {
                "claim_id": "claim-civil-loan-001-02",
                "issue_tmp_ids": ["issue-tmp-001"],
            },
        ],
        "defense_issue_mapping": [
            {
                "defense_id": "defense-civil-loan-001-01",
                "issue_tmp_ids": ["issue-tmp-002"],
            },
            {
                "defense_id": "defense-civil-loan-001-02",
                "issue_tmp_ids": ["issue-tmp-001"],
            },
        ],
    },
    ensure_ascii=False,
)

SAMPLE_CLAIMS = [
    {
        "claim_id": "claim-civil-loan-001-01",
        "case_id": "case-civil-loan-001",
        "title": "归还借款本金50万元",
        "description": "请求被告归还借款本金人民币500,000元",
        "related_evidence_ids": ["evidence-civil-loan-001-01", "evidence-civil-loan-001-02"],
    },
    {
        "claim_id": "claim-civil-loan-001-02",
        "case_id": "case-civil-loan-001",
        "title": "支付利息",
        "description": "请求被告支付逾期利息",
        "related_evidence_ids": ["evidence-civil-loan-001-01"],
    },
]

SAMPLE_DEFENSES = [
    {
        "defense_id": "defense-civil-loan-001-01",
        "case_id": "case-civil-loan-001",
        "title": "已归还20万元",
        "description": "被告主张已通过银行转账归还借款本金20万元",
        "against_claim_id": "claim-civil-loan-001-01",
        "related_evidence_ids": ["evidence-civil-loan-001-03"],
    },
    {
        "defense_id": "defense-civil-loan-001-02",
        "case_id": "case-civil-loan-001",
        "title": "利率约定不明",
        "description": "被告主张双方对利率未作明确约定",
        "against_claim_id": "claim-civil-loan-001-02",
        "related_evidence_ids": ["evidence-civil-loan-001-01"],
    },
]

SAMPLE_EVIDENCE = [
    {
        "evidence_id": "evidence-civil-loan-001-01",
        "case_id": "case-civil-loan-001",
        "title": "借条",
        "evidence_type": "documentary",
        "description": "李四亲笔签名的借条，载明借款金额50万元",
    },
    {
        "evidence_id": "evidence-civil-loan-001-02",
        "case_id": "case-civil-loan-001",
        "title": "转账记录",
        "evidence_type": "documentary",
        "description": "张三向李四银行转账50万元的流水记录",
    },
    {
        "evidence_id": "evidence-civil-loan-001-03",
        "case_id": "case-civil-loan-001",
        "title": "还款凭证",
        "evidence_type": "documentary",
        "description": "李四向张三银行转账20万元的银行流水记录",
    },
]


# ---------------------------------------------------------------------------
# IssueTree 结构测试 / IssueTree structure tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_returns_issue_tree():
    """抽取器应返回 IssueTree 且含有 issues。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    assert isinstance(result, IssueTree)
    assert result.case_id == "case-civil-loan-001"
    assert len(result.issues) == 2
    assert len(result.burdens) == 1


@pytest.mark.asyncio
async def test_issue_ids_use_case_slug():
    """issue_id 应使用 case_slug 自动生成，格式为 issue-{slug}-{seq}。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    ids = [i.issue_id for i in result.issues]
    assert ids == ["issue-civil-loan-001-001", "issue-civil-loan-001-002"]


@pytest.mark.asyncio
async def test_parent_issue_id_resolved():
    """子争点的 parent_issue_id 应解析为正式 ID（非 tmp_id）。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    root_issues = [i for i in result.issues if i.parent_issue_id is None]
    child_issues = [i for i in result.issues if i.parent_issue_id is not None]

    assert len(root_issues) == 1
    assert len(child_issues) == 1

    all_ids = {i.issue_id for i in result.issues}
    for child in child_issues:
        assert child.parent_issue_id in all_ids
        assert not child.parent_issue_id.startswith("issue-tmp-")


@pytest.mark.asyncio
async def test_initial_issue_status_is_open():
    """提取的争点初始状态应为 open。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
    )

    for issue in result.issues:
        assert issue.status == IssueStatus.open


@pytest.mark.asyncio
async def test_fact_propositions_get_ids():
    """每条 FactProposition 应分配 proposition_id，格式为 fp-{slug}-{issue_seq}-{fp_seq}。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    for issue in result.issues:
        for fp in issue.fact_propositions:
            assert fp.proposition_id.startswith("fp-civil-loan-001-")


@pytest.mark.asyncio
async def test_burden_ids_linked_to_root_issues():
    """根争点的 burden_ids 应包含对应 burden 的 ID。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    root = next(i for i in result.issues if i.parent_issue_id is None)
    assert len(root.burden_ids) >= 1
    assert root.burden_ids[0] == "burden-civil-loan-001-001"


# ---------------------------------------------------------------------------
# 映射完整性测试 / Mapping completeness tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_claims_mapped():
    """所有 Claim 应在 claim_issue_mapping 中有对应条目。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
    )

    mapped = {m.claim_id for m in result.claim_issue_mapping}
    for claim in SAMPLE_CLAIMS:
        assert claim["claim_id"] in mapped, f"Claim {claim['claim_id']} not in claim_issue_mapping"


@pytest.mark.asyncio
async def test_all_defenses_mapped():
    """所有 Defense 应在 defense_issue_mapping 中有对应条目。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
    )

    mapped = {m.defense_id for m in result.defense_issue_mapping}
    for defense in SAMPLE_DEFENSES:
        assert defense["defense_id"] in mapped, f"Defense {defense['defense_id']} not in mapping"


# ---------------------------------------------------------------------------
# 提取元数据测试 / Extraction metadata tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extraction_metadata_counts():
    """extraction_metadata 应正确统计处理数量。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
    )

    assert result.extraction_metadata is not None
    assert result.extraction_metadata.total_claims_processed == len(SAMPLE_CLAIMS)
    assert result.extraction_metadata.total_defenses_processed == len(SAMPLE_DEFENSES)
    assert result.extraction_metadata.total_evidence_referenced == len(SAMPLE_EVIDENCE)


# ---------------------------------------------------------------------------
# 输入校验测试 / Input validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_claims_raises_value_error():
    """claims 为空时应抛出 ValueError。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    with pytest.raises(ValueError, match="claims 列表不能为空"):
        await extractor.extract(
            claims=[],
            defenses=SAMPLE_DEFENSES,
            evidence=SAMPLE_EVIDENCE,
            case_id="case-test",
        )


@pytest.mark.asyncio
async def test_duplicate_claim_id_raises():
    """claims 中 claim_id 重复应抛出 ValueError。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    dup_claims = [
        {"claim_id": "claim-dup", "title": "A", "description": "A", "case_id": "c1"},
        {"claim_id": "claim-dup", "title": "B", "description": "B", "case_id": "c1"},
    ]
    with pytest.raises(ValueError, match="重复的 claim_id"):
        await extractor.extract(
            claims=dup_claims,
            defenses=[],
            evidence=[],
            case_id="case-test",
        )


@pytest.mark.asyncio
async def test_duplicate_defense_id_raises():
    """defenses 中 defense_id 重复应抛出 ValueError。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    dup_defenses = [
        {"defense_id": "def-dup", "title": "X", "description": "X", "case_id": "c1"},
        {"defense_id": "def-dup", "title": "Y", "description": "Y", "case_id": "c1"},
    ]
    with pytest.raises(ValueError, match="重复的 defense_id"):
        await extractor.extract(
            claims=SAMPLE_CLAIMS,
            defenses=dup_defenses,
            evidence=[],
            case_id="case-test",
        )


@pytest.mark.asyncio
async def test_unsupported_case_type_raises():
    """不支持的案由类型应在初始化时抛出 ValueError。"""
    with pytest.raises(ValueError, match="不支持的案由类型"):
        IssueExtractor(
            llm_client=MockLLMClient(MOCK_LLM_RESPONSE),
            case_type="unknown_case_type_xyz",
        )


# ---------------------------------------------------------------------------
# 重试逻辑测试 / Retry logic tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_retry_succeeds_after_failures():
    """LLM 前两次调用失败后应重试成功（max_retries=3）。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE, fail_times=2)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan", max_retries=3)

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
    )

    assert isinstance(result, IssueTree)
    assert client.call_count == 3  # 2 failures + 1 success


@pytest.mark.asyncio
async def test_llm_retry_exhausted_raises_runtime_error():
    """超过最大重试次数（3）后应抛出 RuntimeError。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE, fail_times=5)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan", max_retries=3)

    with pytest.raises(RuntimeError, match="LLM 调用失败"):
        await extractor.extract(
            claims=SAMPLE_CLAIMS,
            defenses=SAMPLE_DEFENSES,
            evidence=SAMPLE_EVIDENCE,
            case_id="case-civil-loan-001",
        )

    assert client.call_count == 3  # exactly max_retries attempts


@pytest.mark.asyncio
async def test_llm_receives_system_and_user_prompts():
    """LLM 客户端应收到系统提示词和包含案件ID的用户提示词。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
    )

    assert client.call_count == 1
    assert client.last_system is not None
    assert "争点" in client.last_system
    assert client.last_user is not None
    assert "case-civil-loan-001" in client.last_user


# ---------------------------------------------------------------------------
# JSON 解析辅助函数测试 / JSON extraction utility tests
# ---------------------------------------------------------------------------


def test_extract_json_from_markdown_code_block():
    """应能从 markdown 代码块中提取 JSON 对象。"""
    text = '前置文字\n```json\n{"issues": [], "burdens": []}\n```\n后续文字'
    result = _extract_json_object(text)
    assert result == {"issues": [], "burdens": []}


def test_extract_json_plain_object():
    """应能直接解析纯 JSON 对象字符串。"""
    text = '{"issues": [{"title": "test"}], "burdens": []}'
    result = _extract_json_object(text)
    assert "issues" in result


def test_extract_json_with_surrounding_text():
    """应能从含有前后文的文本中提取 JSON 对象。"""
    text = '以下是结果：\n{"issues": [{"title": "争点A"}]}\n提取完毕。'
    result = _extract_json_object(text)
    assert "issues" in result


def test_extract_json_invalid_raises():
    """无法解析时应抛出 ValueError。"""
    with pytest.raises(ValueError):
        _extract_json_object("这不是JSON内容，无法解析")


# ---------------------------------------------------------------------------
# 争点类型解析测试 / Issue type resolution tests
# ---------------------------------------------------------------------------


def test_resolve_issue_type_english_values():
    """英文枚举值应直接映射。"""
    assert _resolve_issue_type("factual") == IssueType.factual
    assert _resolve_issue_type("legal") == IssueType.legal
    assert _resolve_issue_type("procedural") == IssueType.procedural
    assert _resolve_issue_type("mixed") == IssueType.mixed


def test_resolve_issue_type_chinese_values():
    """中文描述应正确映射。"""
    assert _resolve_issue_type("事实争点") == IssueType.factual
    assert _resolve_issue_type("法律争点") == IssueType.legal
    assert _resolve_issue_type("程序争点") == IssueType.procedural
    assert _resolve_issue_type("混合争点") == IssueType.mixed


def test_resolve_issue_type_unknown_defaults_to_factual():
    """未知类型应回退为 factual。"""
    assert _resolve_issue_type("未知争点类型xyz") == IssueType.factual
    assert _resolve_issue_type("") == IssueType.factual


# ---------------------------------------------------------------------------
# burden fallback 测试 / Burden fallback tests
# ---------------------------------------------------------------------------

# LLM 响应中没有为根争点分配 burden
LLM_RESPONSE_NO_BURDEN = json.dumps(
    {
        "issues": [
            {
                "tmp_id": "issue-tmp-001",
                "title": "借贷关系成立",
                "issue_type": "factual",
                "parent_tmp_id": None,
                "related_claim_ids": ["claim-civil-loan-001-01"],
                "related_defense_ids": [],
                "evidence_ids": ["evidence-civil-loan-001-01"],
                "fact_propositions": [],
            },
        ],
        "burdens": [],  # 空 burdens — 根争点缺少 burden
        "claim_issue_mapping": [
            {
                "claim_id": "claim-civil-loan-001-01",
                "issue_tmp_ids": ["issue-tmp-001"],
            },
        ],
        "defense_issue_mapping": [],
    },
    ensure_ascii=False,
)


@pytest.mark.asyncio
async def test_root_issue_gets_fallback_burden_when_llm_omits():
    """当 LLM 未为根争点分配 burden 时，应自动生成默认 burden。
    Root issue should receive a fallback burden when LLM provides none.
    """
    client = MockLLMClient(LLM_RESPONSE_NO_BURDEN)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    root = next(i for i in result.issues if i.parent_issue_id is None)
    assert len(root.burden_ids) >= 1, "Root issue must have at least one burden_id"

    # 对应的 burden 应存在于 burdens 列表中
    burden_ids_in_tree = {b.burden_id for b in result.burdens}
    for bid in root.burden_ids:
        assert bid in burden_ids_in_tree, f"burden_id {bid!r} not found in burdens list"


@pytest.mark.asyncio
async def test_fallback_burden_has_required_fields():
    """自动生成的 burden 应包含 issue_id 和非空 description。
    Auto-generated fallback burden must have issue_id and non-empty description.
    """
    client = MockLLMClient(LLM_RESPONSE_NO_BURDEN)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    root = next(i for i in result.issues if i.parent_issue_id is None)
    fallback_burden = next(b for b in result.burdens if b.burden_id in root.burden_ids)

    assert fallback_burden.issue_id == root.issue_id
    assert fallback_burden.description
    assert fallback_burden.bearer_party_id  # even if "unknown"


@pytest.mark.asyncio
async def test_existing_burden_not_duplicated():
    """LLM 已为根争点分配 burden 时，不应再添加兜底 burden。
    If LLM already assigns a burden to a root issue, no fallback should be added.
    """
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    root = next(i for i in result.issues if i.parent_issue_id is None)
    # MOCK_LLM_RESPONSE 为根争点提供了一个 burden，不应有额外的兜底
    assert len(root.burden_ids) == 1
    assert root.burden_ids[0] == "burden-civil-loan-001-001"


# ---------------------------------------------------------------------------
# evidence_id 引用校验测试 / evidence_id reference validation tests
# ---------------------------------------------------------------------------

# LLM 响应中包含未知 evidence_id 引用
LLM_RESPONSE_UNKNOWN_EVIDENCE = json.dumps(
    {
        "issues": [
            {
                "tmp_id": "issue-tmp-001",
                "title": "借贷关系成立",
                "issue_type": "factual",
                "parent_tmp_id": None,
                "related_claim_ids": ["claim-civil-loan-001-01"],
                "related_defense_ids": [],
                "evidence_ids": [
                    "evidence-civil-loan-001-01",  # 已知
                    "evidence-UNKNOWN-999",          # 未知
                ],
                "fact_propositions": [
                    {
                        "text": "命题A",
                        "status": "supported",
                        "linked_evidence_ids": [
                            "evidence-civil-loan-001-01",  # 已知
                            "evidence-GHOST-000",           # 未知
                        ],
                    }
                ],
            },
        ],
        "burdens": [
            {
                "issue_tmp_id": "issue-tmp-001",
                "bearer_party_id": "party-test",
                "description": "测试举证责任",
                "proof_standard": "高度盖然性",
                "legal_basis": "《民事诉讼法》第67条",
            }
        ],
        "claim_issue_mapping": [
            {
                "claim_id": "claim-civil-loan-001-01",
                "issue_tmp_ids": ["issue-tmp-001"],
            },
        ],
        "defense_issue_mapping": [],
    },
    ensure_ascii=False,
)


@pytest.mark.asyncio
async def test_unknown_evidence_ids_filtered_from_issue():
    """issue.evidence_ids 中未知 evidence_id 应被过滤。
    Unknown evidence_ids in issue.evidence_ids should be filtered out.
    """
    client = MockLLMClient(LLM_RESPONSE_UNKNOWN_EVIDENCE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    issue = result.issues[0]
    assert "evidence-UNKNOWN-999" not in issue.evidence_ids, (
        "Unknown evidence_id should be filtered from issue.evidence_ids"
    )
    assert "evidence-civil-loan-001-01" in issue.evidence_ids


@pytest.mark.asyncio
async def test_unknown_evidence_ids_filtered_from_fact_propositions():
    """FactProposition.linked_evidence_ids 中未知 evidence_id 应被过滤。
    Unknown evidence_ids in linked_evidence_ids should be filtered out.
    """
    client = MockLLMClient(LLM_RESPONSE_UNKNOWN_EVIDENCE)
    extractor = IssueExtractor(llm_client=client, case_type="civil_loan")

    result = await extractor.extract(
        claims=SAMPLE_CLAIMS,
        defenses=SAMPLE_DEFENSES,
        evidence=SAMPLE_EVIDENCE,
        case_id="case-civil-loan-001",
        case_slug="civil-loan-001",
    )

    issue = result.issues[0]
    for fp in issue.fact_propositions:
        assert "evidence-GHOST-000" not in fp.linked_evidence_ids, (
            "Unknown evidence_id should be filtered from fact_proposition.linked_evidence_ids"
        )


# ---------------------------------------------------------------------------
# ValidationReport 测试 / ValidationReport tests
# ---------------------------------------------------------------------------

def test_validate_issue_tree_report_returns_report():
    """validate_issue_tree_report 应返回 ValidationReport 对象，不抛出异常。"""
    from engines.case_structuring.issue_extractor.validator import (
        ValidationReport,
        validate_issue_tree_report,
    )

    # 使用一个简单的争点树字典（schema 文件可能不存在，但函数不应抛出）
    simple_tree = {
        "case_id": "case-test",
        "issues": [],
        "burdens": [],
        "claim_issue_mapping": [],
        "defense_issue_mapping": [],
    }

    report = validate_issue_tree_report(simple_tree)
    assert isinstance(report, ValidationReport)
    # schema 文件可能不存在（CI 环境），但函数不应抛出异常
    # schema file may be absent in CI; function must not raise
