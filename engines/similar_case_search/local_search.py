"""
本地案例索引搜索 — 在本地 JSON 索引中做关键词匹配。
Local case index search — keyword matching against a local JSON index file.

不需要网络请求，纯本地计算。支持案由精确匹配 + 关键词模糊匹配。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .schemas import CaseIndexEntry, CaseKeywords

logger = logging.getLogger(__name__)

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
            for term in search_terms:
                t = term.lower()
                if any(t in kw.lower() or kw.lower() in t for kw in entry.keywords):
                    score += 2.0
                elif t in entry.summary.lower():
                    score += 1.0

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:max_results]]
