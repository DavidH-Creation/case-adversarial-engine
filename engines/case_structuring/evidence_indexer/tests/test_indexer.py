"""
EvidenceIndexer 单元测试。

使用 mock LLM 客户端验证：
- 输出符合 Evidence schema
- ID 自动生成
- 初始状态正确
- 输入校验（source_id 重复检测）
- JSON 解析（含 markdown 代码块）
"""

from __future__ import annotations

import json
import pytest

from engines.case_structuring.evidence_indexer.schemas import (
    AccessDomain,
    Evidence,
    EvidenceStatus,
    RawMaterial,
)
from engines.case_structuring.evidence_indexer.indexer import (
    EvidenceIndexer,
    _extract_json_array,
    _resolve_evidence_type,
)


# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。"""

    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        return self._response


# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

MOCK_LLM_RESPONSE = json.dumps(
    [
        {
            "title": "借条原件",
            "summary": "被告于2024年1月15日向原告出具借条，载明借款金额5万元。",
            "evidence_type": "documentary",
            "source_id": "doc-promissory-note-001",
            "target_facts": ["fact-loan-contract-existence-001", "fact-loan-amount-50000-001"],
            "target_issues": ["issue-loan-contract-validity-001"],
        },
        {
            "title": "银行转账电子回单",
            "summary": "工商银行电子回单显示原告于2024年1月15日向被告转账人民币50,000元。",
            "evidence_type": "electronic_data",
            "source_id": "doc-bank-transfer-001",
            "target_facts": ["fact-loan-disbursement-001"],
            "target_issues": ["issue-repayment-obligation-001"],
        },
    ],
    ensure_ascii=False,
)

SAMPLE_MATERIALS = [
    RawMaterial(
        source_id="doc-promissory-note-001",
        text="借条。今借到王某某人民币伍万元整...",
        metadata={
            "document_type": "promissory_note",
            "date": "2024-01-15",
            "submitter": "party-plaintiff-002",
        },
    ),
    RawMaterial(
        source_id="doc-bank-transfer-001",
        text="中国工商银行电子回单...",
        metadata={
            "document_type": "bank_transfer_receipt",
            "date": "2024-01-15",
            "submitter": "party-plaintiff-002",
        },
    ),
]


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_produces_valid_evidences():
    """索引器应返回 Evidence 列表且字段齐全。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    evidences = await indexer.index(
        materials=SAMPLE_MATERIALS,
        case_id="case-civil-loan-002",
        owner_party_id="party-plaintiff-002",
    )

    assert len(evidences) == 2
    for e in evidences:
        assert isinstance(e, Evidence)
        assert e.case_id == "case-civil-loan-002"
        assert e.owner_party_id == "party-plaintiff-002"


@pytest.mark.asyncio
async def test_initial_status_and_access_domain():
    """新索引的证据状态必须为 private / owner_private。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    evidences = await indexer.index(
        materials=SAMPLE_MATERIALS,
        case_id="case-civil-loan-002",
        owner_party_id="party-plaintiff-002",
    )

    for e in evidences:
        assert e.status == EvidenceStatus.private
        assert e.access_domain == AccessDomain.owner_private
        assert e.submitted_by_party_id is None
        assert e.challenged_by_party_ids == []
        assert e.admissibility_notes is None


@pytest.mark.asyncio
async def test_evidence_id_generation():
    """evidence_id 应自动生成且在批次内唯一。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    evidences = await indexer.index(
        materials=SAMPLE_MATERIALS,
        case_id="case-civil-loan-002",
        owner_party_id="party-plaintiff-002",
    )

    ids = [e.evidence_id for e in evidences]
    # 所有 ID 唯一
    assert len(ids) == len(set(ids))
    # 所有 ID 以 evidence- 开头
    for eid in ids:
        assert eid.startswith("evidence-")


@pytest.mark.asyncio
async def test_target_fact_ids_non_empty():
    """每条 Evidence 必须绑定至少一条 target_fact_id。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    evidences = await indexer.index(
        materials=SAMPLE_MATERIALS,
        case_id="case-civil-loan-002",
        owner_party_id="party-plaintiff-002",
    )

    for e in evidences:
        assert len(e.target_fact_ids) >= 1


@pytest.mark.asyncio
async def test_duplicate_source_id_raises():
    """输入材料中 source_id 重复应报错。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    duplicate_materials = [
        RawMaterial(source_id="doc-001", text="文本1", metadata={}),
        RawMaterial(source_id="doc-001", text="文本2", metadata={}),
    ]

    with pytest.raises(ValueError, match="重复的 source_id"):
        await indexer.index(
            materials=duplicate_materials,
            case_id="case-test",
            owner_party_id="party-test",
        )


@pytest.mark.asyncio
async def test_llm_client_receives_prompt():
    """LLM 客户端应收到包含案件信息的 prompt。"""
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    await indexer.index(
        materials=SAMPLE_MATERIALS,
        case_id="case-civil-loan-002",
        owner_party_id="party-plaintiff-002",
    )

    assert client.call_count == 1
    assert client.last_system is not None
    assert "证据分析" in client.last_system
    assert client.last_user is not None
    assert "case-civil-loan-002" in client.last_user


# ---------------------------------------------------------------------------
# JSON 解析辅助函数测试
# ---------------------------------------------------------------------------


def test_extract_json_from_code_block():
    """应能从 markdown 代码块中提取 JSON。"""
    text = '这是一些前置文字\n```json\n[{"title": "test"}]\n```\n后续文字'
    result = _extract_json_array(text)
    assert result == [{"title": "test"}]


def test_extract_json_plain():
    """应能解析纯 JSON 文本。"""
    text = '[{"title": "test"}]'
    result = _extract_json_array(text)
    assert result == [{"title": "test"}]


def test_extract_json_with_surrounding_text():
    """应能从含有前后文的文本中提取 JSON 数组。"""
    text = '以下是结果：\n[{"title": "test"}]\n提取完毕。'
    result = _extract_json_array(text)
    assert result == [{"title": "test"}]


def test_extract_json_invalid_raises():
    """无法解析时应抛出 ValueError。"""
    with pytest.raises(ValueError, match="无法从 LLM 响应中解析"):
        _extract_json_array("这不是JSON")


# ---------------------------------------------------------------------------
# 证据类型映射测试
# ---------------------------------------------------------------------------


def test_resolve_evidence_type_chinese():
    """中文证据类型应正确映射。"""
    from engines.case_structuring.evidence_indexer.schemas import EvidenceType

    assert _resolve_evidence_type("书证") == EvidenceType.documentary
    assert _resolve_evidence_type("电子数据") == EvidenceType.electronic_data
    assert _resolve_evidence_type("证人证言") == EvidenceType.witness_statement


def test_resolve_evidence_type_english():
    """英文证据类型应直接映射。"""
    from engines.case_structuring.evidence_indexer.schemas import EvidenceType

    assert _resolve_evidence_type("documentary") == EvidenceType.documentary
    assert _resolve_evidence_type("electronic_data") == EvidenceType.electronic_data


def test_resolve_evidence_type_unknown():
    """未知类型应回退为 other。"""
    from engines.case_structuring.evidence_indexer.schemas import EvidenceType

    assert _resolve_evidence_type("未知类型xyz") == EvidenceType.other


# ---------------------------------------------------------------------------
# 原子批处理测试 / Atomic batch processing tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_failure_aborts_entire_batch():
    """任一 LLM 输出项解析失败应中止整批，抛出 ValueError。
    Any parse failure in LLM output must abort the entire batch.
    """
    # title 字段缺失会导致 LLMEvidenceItem 验证失败
    # Missing required field 'title' causes LLMEvidenceItem validation failure
    bad_response = json.dumps(
        [
            {
                "title": "正常项",
                "summary": "正常摘要",
                "evidence_type": "documentary",
                "source_id": "doc-promissory-note-001",
                "target_facts": ["fact-001"],
            },
            {
                # 缺少 title / missing required title
                "summary": "损坏项",
                "evidence_type": "documentary",
                "source_id": "doc-bank-transfer-001",
            },
        ],
        ensure_ascii=False,
    )

    client = MockLLMClient(bad_response)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    with pytest.raises(ValueError, match="批处理失败"):
        await indexer.index(
            materials=SAMPLE_MATERIALS,
            case_id="case-test",
            owner_party_id="party-test",
        )


# ---------------------------------------------------------------------------
# source_coverage 校验测试 / Source coverage validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_source_coverage_passes_when_all_covered():
    """所有 source_id 均有对应 Evidence 时不应报错。
    No error when all source_ids are covered by evidences.
    """
    client = MockLLMClient(MOCK_LLM_RESPONSE)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    # MOCK_LLM_RESPONSE 包含 doc-promissory-note-001 和 doc-bank-transfer-001
    # 恰好与 SAMPLE_MATERIALS 一致
    evidences = await indexer.index(
        materials=SAMPLE_MATERIALS,
        case_id="case-civil-loan-002",
        owner_party_id="party-plaintiff-002",
    )
    assert len(evidences) == 2


@pytest.mark.asyncio
async def test_source_coverage_fails_when_uncovered():
    """有 source_id 未被任何 LLM 输出覆盖时应抛出 ValueError。
    ValueError raised when some source_id has no corresponding Evidence.
    """
    # LLM 只返回一条证据，但输入有两条材料
    # LLM returns only one evidence, but input has two materials
    partial_response = json.dumps(
        [
            {
                "title": "借条原件",
                "summary": "借条摘要",
                "evidence_type": "documentary",
                "source_id": "doc-promissory-note-001",
                "target_facts": ["fact-001"],
                "target_issues": [],
            },
        ],
        ensure_ascii=False,
    )

    client = MockLLMClient(partial_response)
    indexer = EvidenceIndexer(llm_client=client, case_type="civil_loan")

    with pytest.raises(ValueError, match="source_coverage"):
        await indexer.index(
            materials=SAMPLE_MATERIALS,
            case_id="case-test",
            owner_party_id="party-test",
        )


# ---------------------------------------------------------------------------
# ValidationReport 测试 / ValidationReport tests
# ---------------------------------------------------------------------------


def test_validate_evidence_report_returns_report():
    """validate_evidence_report 应返回 ValidationReport 对象。"""
    from engines.case_structuring.evidence_indexer.validator import (
        ValidationReport,
        validate_evidence_report,
    )

    valid_evidence = {
        "evidence_id": "evidence-test-001",
        "case_id": "case-test",
        "owner_party_id": "party-test",
        "title": "测试证据",
        "source": "doc-001",
        "summary": "这是一条测试证据摘要",
        "evidence_type": "documentary",
        "target_fact_ids": ["fact-001"],
        "access_domain": "owner_private",
        "status": "private",
        "challenged_by_party_ids": [],
    }

    report = validate_evidence_report([valid_evidence])
    assert isinstance(report, ValidationReport)
    # schema 文件可能不存在（CI 环境），但函数不应抛出异常
    # schema file may be absent in CI; function must not raise
