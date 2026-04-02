> Historical document.
> Archived during the April 2026 documentation reorganization.
> Kept for context only. Do not treat this file as the current source of truth.
# Similar Case Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-index-based similar case search module that extracts keywords from the current case, matches against a local court case index, ranks results by LLM, and renders a "类案检索参考" section in the DOCX report.

**Architecture:** Three-stage pipeline (KeywordExtractor → LocalCaseSearcher → RelevanceRanker) in `engines/similar_case_search/`, with a local JSON index at `data/court_cases_index.json`. Results passed as optional parameter to `generate_docx_report()` which renders a new appendix section. CLI integration via `--with-similar-cases` flag.

**Tech Stack:** Pydantic 2, anthropic SDK (via project's LLMClient protocol + `call_structured_llm`), python-docx, pytest + pytest-asyncio

---

## File Structure

```
engines/similar_case_search/
├── __init__.py              # Public API exports
├── models.py                # Pydantic models (CaseKeywords, CaseIndexEntry, RankedCase, etc.)
├── keyword_extractor.py     # LLM-based keyword extraction from case data
├── local_search.py          # Local JSON index search (no network)
└── relevance_ranker.py      # LLM-based semantic relevance ranking

engines/similar_case_search/tests/
├── __init__.py
├── test_models.py           # Model validation tests
├── test_keyword_extractor.py
├── test_local_search.py
└── test_relevance_ranker.py

data/
└── court_cases_index.json   # Local case index (sample data)

# Modified files:
# engines/report_generation/docx_generator.py  — add similar_cases param + _render_similar_cases()
# scripts/run_case.py                          — add --with-similar-cases flag + pipeline step
# pyproject.toml                               — add test paths
```

---

### Task 1: Pydantic Data Models

**Files:**
- Create: `engines/similar_case_search/__init__.py`
- Create: `engines/similar_case_search/models.py`
- Create: `engines/similar_case_search/tests/__init__.py`
- Test: `engines/similar_case_search/tests/test_models.py`

- [ ] **Step 1: Write test for models**

```python
# engines/similar_case_search/tests/test_models.py
"""类案搜索数据模型测试。"""
from __future__ import annotations

import pytest
from engines.similar_case_search.models import (
    CaseKeywords,
    CaseIndexEntry,
    RankedCase,
    RelevanceScore,
)


class TestCaseKeywords:
    def test_valid_keywords(self):
        kw = CaseKeywords(
            cause_of_action="民间借贷纠纷",
            legal_relations=["借贷合同关系"],
            dispute_focuses=["借款金额争议", "利息计算"],
            relevant_statutes=["《民法典》第六百六十七条"],
            search_terms=["民间借贷", "借条", "还款"],
        )
        assert kw.cause_of_action == "民间借贷纠纷"
        assert len(kw.search_terms) == 3

    def test_keywords_requires_cause(self):
        with pytest.raises(Exception):
            CaseKeywords(
                cause_of_action="",
                legal_relations=[],
                dispute_focuses=[],
                relevant_statutes=[],
                search_terms=[],
            )


class TestCaseIndexEntry:
    def test_valid_entry(self):
        entry = CaseIndexEntry(
            case_number="（2024）最高法民再1号",
            court="最高人民法院",
            cause_of_action="民间借贷纠纷",
            keywords=["民间借贷", "利息"],
            summary="关于民间借贷利率上限的认定标准。",
            url="https://rmfyalk.court.gov.cn/ws/detail/1234",
        )
        assert entry.case_number == "（2024）最高法民再1号"

    def test_entry_requires_case_number(self):
        with pytest.raises(Exception):
            CaseIndexEntry(
                case_number="",
                court="某法院",
                cause_of_action="纠纷",
                keywords=[],
                summary="摘要",
                url="https://example.com",
            )


class TestRankedCase:
    def test_valid_ranked_case(self):
        entry = CaseIndexEntry(
            case_number="（2024）最高法民再1号",
            court="最高人民法院",
            cause_of_action="民间借贷纠纷",
            keywords=["民间借贷"],
            summary="关于民间借贷利率认定。",
            url="https://rmfyalk.court.gov.cn/ws/detail/1234",
        )
        rc = RankedCase(
            case=entry,
            relevance=RelevanceScore(
                fact_similarity=0.8,
                legal_relation_similarity=0.9,
                dispute_focus_similarity=0.7,
                judgment_reference_value=0.85,
                overall=0.81,
            ),
            analysis="本案与当前案件在借贷关系认定上高度相似。",
        )
        assert rc.relevance.overall == 0.81

    def test_score_range(self):
        with pytest.raises(Exception):
            RelevanceScore(
                fact_similarity=1.5,  # out of range
                legal_relation_similarity=0.9,
                dispute_focus_similarity=0.7,
                judgment_reference_value=0.85,
                overall=0.81,
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/test_models.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement models**

```python
# engines/similar_case_search/models.py
"""
类案搜索数据模型。
Similar case search data models.

包含关键词提取结果、案例索引条目、相关性评分、排序后案例等模型。
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CaseKeywords(BaseModel):
    """LLM 提取的案件搜索关键词。"""

    cause_of_action: str = Field(..., min_length=1, description="案由")
    legal_relations: list[str] = Field(default_factory=list, description="法律关系")
    dispute_focuses: list[str] = Field(default_factory=list, description="争议焦点")
    relevant_statutes: list[str] = Field(default_factory=list, description="相关法条")
    search_terms: list[str] = Field(default_factory=list, description="搜索关键词")


class CaseIndexEntry(BaseModel):
    """本地案例索引中的单条记录。"""

    case_number: str = Field(..., min_length=1, description="案号")
    court: str = Field(..., min_length=1, description="审理法院")
    cause_of_action: str = Field(..., min_length=1, description="案由")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    summary: str = Field(default="", description="一句话摘要")
    url: str = Field(default="", description="案例库链接")


class RelevanceScore(BaseModel):
    """LLM 语义相关性评分（0.0 ~ 1.0）。"""

    fact_similarity: float = Field(..., ge=0.0, le=1.0, description="事实相似度")
    legal_relation_similarity: float = Field(..., ge=0.0, le=1.0, description="法律关系相似度")
    dispute_focus_similarity: float = Field(..., ge=0.0, le=1.0, description="争议焦点相似度")
    judgment_reference_value: float = Field(..., ge=0.0, le=1.0, description="裁判参考价值")
    overall: float = Field(..., ge=0.0, le=1.0, description="综合评分")


class RankedCase(BaseModel):
    """经 LLM 排序后的类案结果。"""

    case: CaseIndexEntry
    relevance: RelevanceScore
    analysis: str = Field(default="", description="与本案相关性分析")


# LLM 中间结构（用于 call_structured_llm 解析）

class LLMKeywordsOutput(BaseModel):
    """LLM 返回的关键词提取结果（中间结构）。"""

    cause_of_action: str
    legal_relations: list[str] = Field(default_factory=list)
    dispute_focuses: list[str] = Field(default_factory=list)
    relevant_statutes: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)


class LLMRankedItem(BaseModel):
    """LLM 返回的单条排序结果（中间结构）。"""

    case_number: str
    fact_similarity: float
    legal_relation_similarity: float
    dispute_focus_similarity: float
    judgment_reference_value: float
    overall: float
    analysis: str = ""
```

```python
# engines/similar_case_search/__init__.py
"""
类案搜索引擎 — Similar Case Search Engine.

基于本地案例索引的类案检索：关键词提取 → 本地搜索 → 语义排序。
"""
from .models import (
    CaseIndexEntry,
    CaseKeywords,
    RankedCase,
    RelevanceScore,
)

__all__ = [
    "CaseIndexEntry",
    "CaseKeywords",
    "RankedCase",
    "RelevanceScore",
]
```

```python
# engines/similar_case_search/tests/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/test_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add engines/similar_case_search/__init__.py engines/similar_case_search/models.py engines/similar_case_search/tests/__init__.py engines/similar_case_search/tests/test_models.py
git commit -m "feat(similar-case): add Pydantic data models for case search"
```

---

### Task 2: Local Case Index Data

**Files:**
- Create: `data/court_cases_index.json`

- [ ] **Step 1: Create sample index data**

Create `data/court_cases_index.json` with 8-10 sample entries covering common civil case types (民间借贷纠纷、买卖合同纠纷、房屋租赁合同纠纷、劳动争议、离婚纠纷等). Each entry must have realistic case numbers, courts, keywords, and summaries. URLs should use the `rmfyalk.court.gov.cn` domain pattern.

Example structure:
```json
[
  {
    "case_number": "（2024）最高法民再1号",
    "court": "最高人民法院",
    "cause_of_action": "民间借贷纠纷",
    "keywords": ["民间借贷", "利率上限", "LPR四倍"],
    "summary": "关于民间借贷利率保护上限适用标准的认定，明确以一年期LPR的四倍为标准。",
    "url": "https://rmfyalk.court.gov.cn/ws/detail/2024-zgf-mr-00001"
  }
]
```

- [ ] **Step 2: Commit**

```bash
git add data/court_cases_index.json
git commit -m "feat(similar-case): add sample court case index data"
```

---

### Task 3: Keyword Extractor

**Files:**
- Create: `engines/similar_case_search/keyword_extractor.py`
- Test: `engines/similar_case_search/tests/test_keyword_extractor.py`

- [ ] **Step 1: Write test for KeywordExtractor**

```python
# engines/similar_case_search/tests/test_keyword_extractor.py
"""关键词提取器测试。"""
from __future__ import annotations

import json
import pytest

from engines.similar_case_search.keyword_extractor import KeywordExtractor
from engines.similar_case_search.models import CaseKeywords


class MockLLMClient:
    """返回预定义 JSON 响应的 mock LLM 客户端。"""

    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count = 0
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        self.last_system = system
        self.last_user = user
        return self._response


MOCK_KEYWORDS_RESPONSE = json.dumps(
    {
        "cause_of_action": "民间借贷纠纷",
        "legal_relations": ["借贷合同关系", "保证担保关系"],
        "dispute_focuses": ["借款金额争议", "利息计算标准"],
        "relevant_statutes": ["《民法典》第六百六十七条"],
        "search_terms": ["民间借贷", "借条", "利息", "还款期限"],
    },
    ensure_ascii=False,
)

SAMPLE_CASE_DATA = {
    "case_id": "case-civil-loan-001",
    "case_type": "civil_loan",
    "parties": {
        "plaintiff": {"party_id": "p1", "name": "王某"},
        "defendant": {"party_id": "d1", "name": "陈某"},
    },
    "summary": [["核心争议", "被告是否偿还了借款50000元"]],
    "claims": [{"claim_id": "c1", "text": "要求被告偿还借款50000元及利息"}],
    "defenses": [{"defense_id": "d1", "text": "已通过微信转账偿还全部借款"}],
}


@pytest.mark.asyncio
async def test_extract_returns_case_keywords():
    client = MockLLMClient(MOCK_KEYWORDS_RESPONSE)
    extractor = KeywordExtractor(llm_client=client)
    result = await extractor.extract(SAMPLE_CASE_DATA)

    assert isinstance(result, CaseKeywords)
    assert result.cause_of_action == "民间借贷纠纷"
    assert len(result.search_terms) == 4
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_extract_includes_case_context_in_prompt():
    client = MockLLMClient(MOCK_KEYWORDS_RESPONSE)
    extractor = KeywordExtractor(llm_client=client)
    await extractor.extract(SAMPLE_CASE_DATA)

    assert "王某" in client.last_user
    assert "陈某" in client.last_user
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/test_keyword_extractor.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement KeywordExtractor**

```python
# engines/similar_case_search/keyword_extractor.py
"""
关键词提取器 — 用 LLM 从案件数据提取搜索关键词。
Keyword extractor — uses LLM to extract search keywords from case data.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

from engines.shared.structured_output import call_structured_llm

from .models import CaseKeywords, LLMKeywordsOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一名资深中国法律检索专家。根据提供的案件信息，提取适合在人民法院案例库中搜索类案的关键词。

要求：
1. 准确识别案由（如：民间借贷纠纷、买卖合同纠纷等）
2. 提取核心法律关系
3. 识别主要争议焦点
4. 列出相关法条
5. 生成 3-8 个搜索关键词，覆盖案由、核心事实、法律要点
"""

_TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "cause_of_action": {
            "type": "string",
            "description": "案由（如：民间借贷纠纷）",
        },
        "legal_relations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "核心法律关系列表",
        },
        "dispute_focuses": {
            "type": "array",
            "items": {"type": "string"},
            "description": "主要争议焦点列表",
        },
        "relevant_statutes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "相关法条列表",
        },
        "search_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "搜索关键词列表（3-8个）",
        },
    },
    "required": [
        "cause_of_action",
        "legal_relations",
        "dispute_focuses",
        "relevant_statutes",
        "search_terms",
    ],
}


class KeywordExtractor:
    """从案件数据中提取类案搜索关键词。"""

    def __init__(
        self,
        llm_client: "LLMClient",
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

    async def extract(self, case_data: dict[str, Any]) -> CaseKeywords:
        """从案件数据提取搜索关键词。"""
        user_prompt = self._build_user_prompt(case_data)
        logger.info("提取类案搜索关键词...")

        data = await call_structured_llm(
            self._llm,
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            model=self._model,
            tool_name="extract_case_keywords",
            tool_description="从案件信息中提取类案搜索关键词",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )

        output = LLMKeywordsOutput.model_validate(data)
        return CaseKeywords(
            cause_of_action=output.cause_of_action,
            legal_relations=output.legal_relations,
            dispute_focuses=output.dispute_focuses,
            relevant_statutes=output.relevant_statutes,
            search_terms=output.search_terms,
        )

    def _build_user_prompt(self, case_data: dict[str, Any]) -> str:
        """构建用户提示词，包含案件核心信息。"""
        parts: list[str] = []

        # 当事人
        parties = case_data.get("parties", {})
        for role, info in parties.items():
            name = info.get("name", "")
            if name:
                role_zh = "原告" if "plaintiff" in role else "被告"
                parts.append(f"{role_zh}：{name}")

        # 案件摘要
        for row in case_data.get("summary", []):
            if isinstance(row, list) and len(row) >= 2:
                parts.append(f"{row[0]}：{row[1]}")

        # 诉讼请求
        claims = case_data.get("claims", [])
        if claims:
            parts.append("诉讼请求：")
            for c in claims:
                text = c.get("text", "") if isinstance(c, dict) else str(c)
                if text:
                    parts.append(f"  - {text}")

        # 抗辩
        defenses = case_data.get("defenses", [])
        if defenses:
            parts.append("被告抗辩：")
            for d in defenses:
                text = d.get("text", "") if isinstance(d, dict) else str(d)
                if text:
                    parts.append(f"  - {text}")

        # 案件类型
        case_type = case_data.get("case_type", "")
        if case_type:
            parts.append(f"案件类型：{case_type}")

        return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/test_keyword_extractor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add engines/similar_case_search/keyword_extractor.py engines/similar_case_search/tests/test_keyword_extractor.py
git commit -m "feat(similar-case): add LLM keyword extractor"
```

---

### Task 4: Local Search

**Files:**
- Create: `engines/similar_case_search/local_search.py`
- Test: `engines/similar_case_search/tests/test_local_search.py`

- [ ] **Step 1: Write test for LocalCaseSearcher**

```python
# engines/similar_case_search/tests/test_local_search.py
"""本地案例索引搜索测试。"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from engines.similar_case_search.local_search import LocalCaseSearcher
from engines.similar_case_search.models import CaseIndexEntry, CaseKeywords


SAMPLE_INDEX = [
    {
        "case_number": "（2024）最高法民再1号",
        "court": "最高人民法院",
        "cause_of_action": "民间借贷纠纷",
        "keywords": ["民间借贷", "利率上限", "LPR四倍"],
        "summary": "关于民间借贷利率保护上限适用标准。",
        "url": "https://rmfyalk.court.gov.cn/ws/detail/001",
    },
    {
        "case_number": "（2024）京01民终2号",
        "court": "北京市第一中级人民法院",
        "cause_of_action": "买卖合同纠纷",
        "keywords": ["买卖合同", "质量瑕疵", "违约金"],
        "summary": "买卖合同中质量瑕疵的认定标准。",
        "url": "https://rmfyalk.court.gov.cn/ws/detail/002",
    },
    {
        "case_number": "（2024）沪02民终3号",
        "court": "上海市第二中级人民法院",
        "cause_of_action": "民间借贷纠纷",
        "keywords": ["民间借贷", "借条", "还款期限"],
        "summary": "借条载明的还款期限与实际履行的认定。",
        "url": "https://rmfyalk.court.gov.cn/ws/detail/003",
    },
]


@pytest.fixture
def index_file(tmp_path: Path) -> Path:
    p = tmp_path / "index.json"
    p.write_text(json.dumps(SAMPLE_INDEX, ensure_ascii=False), encoding="utf-8")
    return p


class TestLocalCaseSearcher:
    def test_search_by_cause_of_action(self, index_file: Path):
        searcher = LocalCaseSearcher(index_path=index_file)
        keywords = CaseKeywords(
            cause_of_action="民间借贷纠纷",
            legal_relations=[],
            dispute_focuses=[],
            relevant_statutes=[],
            search_terms=[],
        )
        results = searcher.search(keywords)
        # 案由完全匹配的应排在前面
        assert len(results) >= 2
        assert all(r.cause_of_action == "民间借贷纠纷" for r in results[:2])

    def test_search_by_keywords(self, index_file: Path):
        searcher = LocalCaseSearcher(index_path=index_file)
        keywords = CaseKeywords(
            cause_of_action="其他纠纷",
            legal_relations=[],
            dispute_focuses=[],
            relevant_statutes=[],
            search_terms=["借条", "还款"],
        )
        results = searcher.search(keywords)
        assert len(results) >= 1
        # 包含"借条"关键词的案例应被匹配
        matched_numbers = {r.case_number for r in results}
        assert "（2024）沪02民终3号" in matched_numbers

    def test_search_with_max_results(self, index_file: Path):
        searcher = LocalCaseSearcher(index_path=index_file)
        keywords = CaseKeywords(
            cause_of_action="民间借贷纠纷",
            legal_relations=[],
            dispute_focuses=[],
            relevant_statutes=[],
            search_terms=["民间借贷"],
        )
        results = searcher.search(keywords, max_results=1)
        assert len(results) == 1

    def test_search_no_match(self, index_file: Path):
        searcher = LocalCaseSearcher(index_path=index_file)
        keywords = CaseKeywords(
            cause_of_action="知识产权纠纷",
            legal_relations=[],
            dispute_focuses=[],
            relevant_statutes=[],
            search_terms=["专利侵权"],
        )
        results = searcher.search(keywords)
        assert len(results) == 0

    def test_missing_index_file(self, tmp_path: Path):
        searcher = LocalCaseSearcher(index_path=tmp_path / "nonexistent.json")
        keywords = CaseKeywords(
            cause_of_action="民间借贷纠纷",
            legal_relations=[],
            dispute_focuses=[],
            relevant_statutes=[],
            search_terms=[],
        )
        results = searcher.search(keywords)
        assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/test_local_search.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement LocalCaseSearcher**

```python
# engines/similar_case_search/local_search.py
"""
本地案例索引搜索 — 在本地 JSON 索引中做关键词匹配。
Local case index search — keyword matching against a local JSON index file.

不需要网络请求，纯本地计算。支持案由精确匹配 + 关键词模糊匹配。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import CaseIndexEntry, CaseKeywords

logger = logging.getLogger(__name__)

# 项目根目录下的默认索引路径
_DEFAULT_INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "court_cases_index.json"


class LocalCaseSearcher:
    """在本地案例索引中搜索匹配的案例。"""

    def __init__(self, index_path: Path | None = None) -> None:
        self._index_path = index_path or _DEFAULT_INDEX_PATH
        self._entries: list[CaseIndexEntry] | None = None

    def _load_index(self) -> list[CaseIndexEntry]:
        """加载并缓存索引数据。"""
        if self._entries is not None:
            return self._entries

        if not self._index_path.exists():
            logger.warning("案例索引文件不存在: %s", self._index_path)
            self._entries = []
            return self._entries

        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._entries = [CaseIndexEntry.model_validate(item) for item in raw]
            logger.info("已加载 %d 条案例索引", len(self._entries))
        except Exception:
            logger.exception("加载案例索引失败")
            self._entries = []

        return self._entries

    def search(
        self,
        keywords: CaseKeywords,
        max_results: int = 20,
    ) -> list[CaseIndexEntry]:
        """搜索匹配的案例，按匹配度降序返回。

        匹配逻辑：
        1. 案由完全匹配得 3 分
        2. 案由部分匹配得 1 分
        3. 每个搜索关键词命中案例关键词得 2 分
        4. 每个搜索关键词命中案例摘要得 1 分
        """
        entries = self._load_index()
        if not entries:
            return []

        scored: list[tuple[float, CaseIndexEntry]] = []
        search_terms = keywords.search_terms + keywords.dispute_focuses

        for entry in entries:
            score = 0.0

            # 案由匹配
            if entry.cause_of_action == keywords.cause_of_action:
                score += 3.0
            elif keywords.cause_of_action in entry.cause_of_action:
                score += 1.0
            elif entry.cause_of_action in keywords.cause_of_action:
                score += 1.0

            # 关键词匹配
            entry_kw_text = " ".join(entry.keywords).lower()
            entry_summary = entry.summary.lower()

            for term in search_terms:
                t = term.lower()
                if any(t in kw.lower() or kw.lower() in t for kw in entry.keywords):
                    score += 2.0
                elif t in entry_summary:
                    score += 1.0

            if score > 0:
                scored.append((score, entry))

        # 按分数降序排列
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:max_results]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/test_local_search.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add engines/similar_case_search/local_search.py engines/similar_case_search/tests/test_local_search.py
git commit -m "feat(similar-case): add local case index searcher"
```

---

### Task 5: Relevance Ranker

**Files:**
- Create: `engines/similar_case_search/relevance_ranker.py`
- Test: `engines/similar_case_search/tests/test_relevance_ranker.py`

- [ ] **Step 1: Write test for RelevanceRanker**

```python
# engines/similar_case_search/tests/test_relevance_ranker.py
"""相关性排序器测试。"""
from __future__ import annotations

import json
import pytest

from engines.similar_case_search.relevance_ranker import RelevanceRanker
from engines.similar_case_search.models import CaseIndexEntry, RankedCase


class MockLLMClient:
    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count = 0

    async def create_message(self, *, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        return self._response


SAMPLE_CANDIDATES = [
    CaseIndexEntry(
        case_number="（2024）最高法民再1号",
        court="最高人民法院",
        cause_of_action="民间借贷纠纷",
        keywords=["民间借贷", "利率上限"],
        summary="关于民间借贷利率保护上限适用标准。",
        url="https://rmfyalk.court.gov.cn/ws/detail/001",
    ),
    CaseIndexEntry(
        case_number="（2024）沪02民终3号",
        court="上海市第二中级人民法院",
        cause_of_action="民间借贷纠纷",
        keywords=["民间借贷", "借条"],
        summary="借条载明的还款期限认定。",
        url="https://rmfyalk.court.gov.cn/ws/detail/003",
    ),
]

MOCK_RANKER_RESPONSE = json.dumps(
    {
        "ranked_cases": [
            {
                "case_number": "（2024）最高法民再1号",
                "fact_similarity": 0.8,
                "legal_relation_similarity": 0.9,
                "dispute_focus_similarity": 0.7,
                "judgment_reference_value": 0.85,
                "overall": 0.81,
                "analysis": "本案与当前案件均涉及民间借贷利率争议，事实基础高度相似。",
            },
            {
                "case_number": "（2024）沪02民终3号",
                "fact_similarity": 0.6,
                "legal_relation_similarity": 0.7,
                "dispute_focus_similarity": 0.5,
                "judgment_reference_value": 0.6,
                "overall": 0.60,
                "analysis": "均涉及借条效力认定，但争议焦点有所不同。",
            },
        ]
    },
    ensure_ascii=False,
)

SAMPLE_CASE_DATA = {
    "case_id": "case-001",
    "case_type": "civil_loan",
    "parties": {
        "plaintiff": {"party_id": "p1", "name": "王某"},
        "defendant": {"party_id": "d1", "name": "陈某"},
    },
    "summary": [["核心争议", "借款利率是否合法"]],
    "claims": [{"claim_id": "c1", "text": "要求偿还借款及利息"}],
    "defenses": [{"defense_id": "d1", "text": "利率过高，超出法定上限"}],
}


@pytest.mark.asyncio
async def test_rank_returns_ranked_cases():
    client = MockLLMClient(MOCK_RANKER_RESPONSE)
    ranker = RelevanceRanker(llm_client=client)

    results = await ranker.rank(SAMPLE_CASE_DATA, SAMPLE_CANDIDATES)

    assert len(results) == 2
    assert all(isinstance(r, RankedCase) for r in results)
    # 按 overall 降序
    assert results[0].relevance.overall >= results[1].relevance.overall
    assert results[0].case.case_number == "（2024）最高法民再1号"
    assert client.call_count == 1


@pytest.mark.asyncio
async def test_rank_empty_candidates():
    client = MockLLMClient("{}")
    ranker = RelevanceRanker(llm_client=client)

    results = await ranker.rank(SAMPLE_CASE_DATA, [])
    assert results == []
    assert client.call_count == 0  # 空列表不调用 LLM
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/test_relevance_ranker.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement RelevanceRanker**

```python
# engines/similar_case_search/relevance_ranker.py
"""
相关性排序器 — 用 LLM 对候选类案做语义相关性排序。
Relevance ranker — uses LLM to rank candidate cases by semantic relevance.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engines.shared.models import LLMClient

from engines.shared.structured_output import call_structured_llm

from .models import CaseIndexEntry, LLMRankedItem, RankedCase, RelevanceScore

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一名资深中国法律案例研究专家。给定一个当前案件和若干候选类案，请从以下四个维度评估每个候选案例与当前案件的相关性：

1. 事实相似度 (fact_similarity): 案件基本事实是否相似
2. 法律关系相似度 (legal_relation_similarity): 涉及的法律关系是否相同
3. 争议焦点相似度 (dispute_focus_similarity): 争议焦点是否一致
4. 裁判参考价值 (judgment_reference_value): 该案判决对当前案件的参考意义

每个维度评分 0.0-1.0，并给出综合评分 (overall) 和简要分析。
按综合评分从高到低排序输出。
"""

_TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "ranked_cases": {
            "type": "array",
            "description": "按相关性排序的案例列表",
            "items": {
                "type": "object",
                "properties": {
                    "case_number": {"type": "string", "description": "案号"},
                    "fact_similarity": {"type": "number"},
                    "legal_relation_similarity": {"type": "number"},
                    "dispute_focus_similarity": {"type": "number"},
                    "judgment_reference_value": {"type": "number"},
                    "overall": {"type": "number"},
                    "analysis": {"type": "string", "description": "相关性分析"},
                },
                "required": [
                    "case_number",
                    "fact_similarity",
                    "legal_relation_similarity",
                    "dispute_focus_similarity",
                    "judgment_reference_value",
                    "overall",
                    "analysis",
                ],
            },
        }
    },
    "required": ["ranked_cases"],
}


class RelevanceRanker:
    """用 LLM 对候选类案进行语义相关性排序。"""

    def __init__(
        self,
        llm_client: "LLMClient",
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> None:
        self._llm = llm_client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

    async def rank(
        self,
        case_data: dict[str, Any],
        candidates: list[CaseIndexEntry],
    ) -> list[RankedCase]:
        """对候选案例做语义相关性排序，返回按 overall 降序排列的结果。"""
        if not candidates:
            return []

        user_prompt = self._build_user_prompt(case_data, candidates)
        logger.info("对 %d 条候选类案进行语义排序...", len(candidates))

        data = await call_structured_llm(
            self._llm,
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            model=self._model,
            tool_name="rank_similar_cases",
            tool_description="对候选类案进行语义相关性评分和排序",
            tool_schema=_TOOL_SCHEMA,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            max_retries=self._max_retries,
        )

        # 构建 case_number → CaseIndexEntry 查找表
        entry_map = {e.case_number: e for e in candidates}

        ranked_items = [LLMRankedItem.model_validate(item) for item in data.get("ranked_cases", [])]

        results: list[RankedCase] = []
        for item in ranked_items:
            entry = entry_map.get(item.case_number)
            if entry is None:
                logger.warning("LLM 返回的案号未在候选列表中: %s", item.case_number)
                continue
            results.append(
                RankedCase(
                    case=entry,
                    relevance=RelevanceScore(
                        fact_similarity=item.fact_similarity,
                        legal_relation_similarity=item.legal_relation_similarity,
                        dispute_focus_similarity=item.dispute_focus_similarity,
                        judgment_reference_value=item.judgment_reference_value,
                        overall=item.overall,
                    ),
                    analysis=item.analysis,
                )
            )

        # 确保按 overall 降序
        results.sort(key=lambda r: r.relevance.overall, reverse=True)
        return results

    def _build_user_prompt(
        self, case_data: dict[str, Any], candidates: list[CaseIndexEntry]
    ) -> str:
        """构建用户提示词。"""
        parts: list[str] = ["## 当前案件信息\n"]

        # 当事人
        parties = case_data.get("parties", {})
        for role, info in parties.items():
            name = info.get("name", "")
            if name:
                role_zh = "原告" if "plaintiff" in role else "被告"
                parts.append(f"{role_zh}：{name}")

        # 摘要
        for row in case_data.get("summary", []):
            if isinstance(row, list) and len(row) >= 2:
                parts.append(f"{row[0]}：{row[1]}")

        # 诉请与抗辩
        for c in case_data.get("claims", []):
            text = c.get("text", "") if isinstance(c, dict) else str(c)
            if text:
                parts.append(f"诉请：{text}")
        for d in case_data.get("defenses", []):
            text = d.get("text", "") if isinstance(d, dict) else str(d)
            if text:
                parts.append(f"抗辩：{text}")

        parts.append("\n## 候选类案\n")
        for i, entry in enumerate(candidates, 1):
            parts.append(
                f"{i}. 案号：{entry.case_number}\n"
                f"   法院：{entry.court}\n"
                f"   案由：{entry.cause_of_action}\n"
                f"   关键词：{', '.join(entry.keywords)}\n"
                f"   摘要：{entry.summary}"
            )

        return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/test_relevance_ranker.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add engines/similar_case_search/relevance_ranker.py engines/similar_case_search/tests/test_relevance_ranker.py
git commit -m "feat(similar-case): add LLM relevance ranker"
```

---

### Task 6: DOCX Report Section

**Files:**
- Modify: `engines/report_generation/docx_generator.py:194-281` (add `similar_cases` param + render call)
- Add: `_render_similar_cases()` function in same file

- [ ] **Step 1: Read docx_generator.py current state at edit points**

Re-read `engines/report_generation/docx_generator.py` lines 194-281 (function signature and section render calls) to get exact current content for edits.

- [ ] **Step 2: Add `similar_cases` parameter to `generate_docx_report()`**

In `engines/report_generation/docx_generator.py`, add `similar_cases: list | None = None` to the function signature (after `document_drafts`), and add the render call before the save:

```python
# After line ~274 (after document_drafts rendering, before save):
    # ── 类案检索参考 ──
    if similar_cases:
        _render_similar_cases(doc, similar_cases)
```

Also add the import at the top of the file.

- [ ] **Step 3: Implement `_render_similar_cases()` function**

Add this function in the section renderers area of `docx_generator.py`:

```python
def _render_similar_cases(doc, similar_cases: list):
    """类案检索参考章节。

    Args:
        similar_cases: list of RankedCase dicts (model_dump output)
    """
    _styled(doc, "类案检索参考", bold=True, size=SZ_SUBTITLE, color=CLR_TITLE_DARK)
    _styled(
        doc,
        "以下案例来源于人民法院案例库（rmfyalk.court.gov.cn），经最高人民法院审核认可，"
        "按与本案相关性由高到低排列。",
        size=SZ_NORMAL,
        color=CLR_GRAY,
    )
    doc.add_paragraph()

    for idx, rc in enumerate(similar_cases, 1):
        case_info = rc.get("case", rc) if isinstance(rc, dict) else rc
        relevance = rc.get("relevance", {}) if isinstance(rc, dict) else {}
        analysis = rc.get("analysis", "") if isinstance(rc, dict) else ""

        # 如果 case_info 是 dict，直接取值；否则尝试属性访问
        if isinstance(case_info, dict):
            case_number = case_info.get("case_number", "")
            court = case_info.get("court", "")
            cause = case_info.get("cause_of_action", "")
            kw_list = case_info.get("keywords", [])
            summary = case_info.get("summary", "")
            url = case_info.get("url", "")
        else:
            case_number = getattr(case_info, "case_number", "")
            court = getattr(case_info, "court", "")
            cause = getattr(case_info, "cause_of_action", "")
            kw_list = getattr(case_info, "keywords", [])
            summary = getattr(case_info, "summary", "")
            url = getattr(case_info, "url", "")

        if isinstance(relevance, dict):
            overall = relevance.get("overall", 0)
        else:
            overall = getattr(relevance, "overall", 0)

        # 标题行
        p_title = doc.add_paragraph()
        _add_run(
            p_title,
            f"类案 {idx}：{case_number}",
            bold=True,
            size=SZ_SECTION_HDR,
            color=CLR_BLUE,
        )

        # 基本信息表格
        table = doc.add_table(rows=5, cols=2, style="Table Grid")
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        fields = [
            ("审理法院", court),
            ("案由", cause),
            ("关键词", "、".join(kw_list) if kw_list else "—"),
            ("裁判要旨", summary or "—"),
            ("相关性评分", f"{overall:.0%}"),
        ]
        for row_idx, (label, value) in enumerate(fields):
            table.cell(row_idx, 0).text = label
            table.cell(row_idx, 1).text = str(value)
        _set_table_font(table)

        # 相关性分析
        if analysis:
            p_analysis = doc.add_paragraph()
            _add_run(p_analysis, "与本案相关性分析：", bold=True, size=SZ_NORMAL, color=CLR_BODY)
            _styled(doc, analysis, size=SZ_NORMAL, color=CLR_BODY)

        # 案例库链接
        if url:
            _styled(doc, f"案例库链接：{url}", size=SZ_EVIDENCE, color=CLR_GRAY)

        doc.add_paragraph()  # 案例间间隔
```

- [ ] **Step 4: Run type check**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -c "from engines.report_generation.docx_generator import generate_docx_report; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add engines/report_generation/docx_generator.py
git commit -m "feat(similar-case): add similar cases section to DOCX report"
```

---

### Task 7: CLI Integration

**Files:**
- Modify: `scripts/run_case.py:1132-1146` (main function signature)
- Modify: `scripts/run_case.py:1525-1562` (STEP_DOCX section — pass similar_cases to generate_docx_report)
- Modify: `scripts/run_case.py:1788-1798` (argparse — add --with-similar-cases)
- Modify: `scripts/run_case.py:1817-1834` (asyncio.run call — pass with_similar_cases)

- [ ] **Step 1: Re-read run_case.py at edit points**

Re-read `scripts/run_case.py` at the four edit regions to get exact current content.

- [ ] **Step 2: Add import for similar case search modules**

After the existing engine imports (around line 124), add:

```python
from engines.similar_case_search.keyword_extractor import KeywordExtractor
from engines.similar_case_search.local_search import LocalCaseSearcher
from engines.similar_case_search.relevance_ranker import RelevanceRanker
```

- [ ] **Step 3: Add `--with-similar-cases` argument**

After the `--with-mediation` argument (around line 1792), add:

```python
parser.add_argument(
    "--with-similar-cases",
    action="store_true",
    help="Search for similar cases in local index and include in report (default: off)",
)
```

- [ ] **Step 4: Add `with_similar_cases` parameter to `main()` signature**

Add `with_similar_cases: bool = False` to `main()` signature (after `with_mediation`).

- [ ] **Step 5: Add similar case search step before DOCX generation**

Before the STEP_DOCX section (around line 1525), add a similar case search block:

```python
    # Step 4.5: Similar case search (optional)
    similar_cases_data = None
    if with_similar_cases:
        print("\n[Step 4.5] Searching for similar cases...")
        try:
            kw_extractor = KeywordExtractor(
                llm_client=claude,
                model=selector.select("keyword_extractor"),
            )
            case_keywords = await kw_extractor.extract(case_data)
            print(f"  关键词: {', '.join(case_keywords.search_terms)}")

            searcher = LocalCaseSearcher()
            candidates = searcher.search(case_keywords, max_results=20)
            print(f"  匹配到 {len(candidates)} 条候选案例")

            if candidates:
                ranker = RelevanceRanker(
                    llm_client=claude,
                    model=selector.select("relevance_ranker"),
                )
                ranked = await ranker.rank(case_data, candidates)
                # 取 top 10
                similar_cases_data = [
                    json.loads(rc.model_dump_json()) for rc in ranked[:10]
                ]
                print(f"  排序完成，取 top {len(similar_cases_data)} 条")
        except Exception as e:
            print(f"  [Warning] Similar case search failed: {e}")
```

- [ ] **Step 6: Pass `similar_cases` to `generate_docx_report()`**

In the STEP_DOCX section, add `similar_cases=similar_cases_data` to the `generate_docx_report()` call.

- [ ] **Step 7: Pass `with_similar_cases` through asyncio.run()**

In the argparse/asyncio.run section, add `with_similar_cases=args.with_similar_cases` to both the `main()` call.

- [ ] **Step 8: Verify syntax**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -c "import scripts.run_case" 2>&1 || python -c "import ast; ast.parse(open('scripts/run_case.py').read()); print('Syntax OK')"`
Expected: Syntax OK (or import OK)

- [ ] **Step 9: Commit**

```bash
git add scripts/run_case.py
git commit -m "feat(similar-case): add --with-similar-cases CLI flag and pipeline step"
```

---

### Task 8: Update __init__.py + pyproject.toml + Final Exports

**Files:**
- Modify: `engines/similar_case_search/__init__.py` (add engine class exports)
- Modify: `pyproject.toml` (add test paths)

- [ ] **Step 1: Update __init__.py with full exports**

```python
# engines/similar_case_search/__init__.py
"""
类案搜索引擎 — Similar Case Search Engine.

基于本地案例索引的类案检索：关键词提取 → 本地搜索 → 语义排序。
"""
from .keyword_extractor import KeywordExtractor
from .local_search import LocalCaseSearcher
from .models import (
    CaseIndexEntry,
    CaseKeywords,
    RankedCase,
    RelevanceScore,
)
from .relevance_ranker import RelevanceRanker

__all__ = [
    "KeywordExtractor",
    "LocalCaseSearcher",
    "RelevanceRanker",
    "CaseIndexEntry",
    "CaseKeywords",
    "RankedCase",
    "RelevanceScore",
]
```

- [ ] **Step 2: Add test paths to pyproject.toml**

In `pyproject.toml`, add to `testpaths`:
```
"engines/similar_case_search/tests",
```

- [ ] **Step 3: Run all similar case search tests**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Run type check**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -c "from engines.similar_case_search import KeywordExtractor, LocalCaseSearcher, RelevanceRanker; print('All exports OK')"`
Expected: All exports OK

- [ ] **Step 5: Commit**

```bash
git add engines/similar_case_search/__init__.py pyproject.toml
git commit -m "feat(similar-case): finalize module exports and test config"
```

---

### Task 9: Integration Verification

- [ ] **Step 1: Run full test suite for similar case search**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/similar_case_search/tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run type check on all modified files**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && npx tsc --noEmit 2>/dev/null; python -c "import py_compile; [py_compile.compile(f, doraise=True) for f in ['engines/similar_case_search/models.py', 'engines/similar_case_search/keyword_extractor.py', 'engines/similar_case_search/local_search.py', 'engines/similar_case_search/relevance_ranker.py', 'engines/report_generation/docx_generator.py']]; print('All compile OK')"`
Expected: All compile OK

- [ ] **Step 3: Verify CLI flag is recognized**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python scripts/run_case.py --help 2>&1 | grep -A1 "with-similar"`
Expected: Shows `--with-similar-cases` in help output

- [ ] **Step 4: Run broader test suite to check nothing broke**

Run: `cd /c/Users/david/dev/case-adversarial-engine/.claude/worktrees/interesting-dewdney && python -m pytest engines/report_generation/tests/ engines/shared/tests/ -v --tb=short -x`
Expected: All existing tests still PASS

