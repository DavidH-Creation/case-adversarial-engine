---
date: 2026-04-01
topic: similar-case-search
---

# 类案搜索模块（Similar Case Search）

## Problem Frame

律师用户需要类案检索功能，搜索人民法院案例库中的类似案件供法庭参考。类案检索报告通常打印提交法庭。人民法院案例库（rmfyalk.court.gov.cn）约3927篇权威案例，量不大，适合本地索引方案。

## Requirements

**数据层**
- R1. 维护本地 JSON 索引文件 `data/court_cases_index.json`，每条记录包含：案号、法院、案由、关键词、一句话摘要、案例库链接
- R2. 提供示例索引数据（民间借贷、合同纠纷等常见民事案由，5-10条）

**关键词提取**
- R3. `keyword_extractor.py` 用 LLM 从当前案件提取搜索关键词组合（案由、法律关系、争议焦点、关键法条）
- R4. 遵循项目 LLMClient 协议，用 `call_structured_llm()` 获取结构化输出

**本地搜索**
- R5. `local_search.py` 在本地索引中做关键词匹配搜索，支持多关键词 OR/AND 组合
- R6. 纯本地计算，不需要网络请求，不需要 Playwright

**相关性排序**
- R7. `relevance_ranker.py` 用 LLM 对匹配结果做语义相关性排序
- R8. 评估维度：事实相似度、法律关系相似度、争议焦点相似度、裁判参考价值
- R9. 输出相关性评分和分析说明

**报告集成**
- R10. 类案结果作为现有 DOCX 报告的新 section 输出（附录区域）
- R11. 每个类案包含：案号、法院、案由、关键词、摘要、与本案相关性分析、案例库链接
- R12. 格式专业，适合打印提交法庭

**CLI 集成**
- R13. `--with-similar-cases` flag 加入 `scripts/run_case.py`，默认关闭
- R14. 开启后在分析完成后自动搜索类案并加入报告

## Design

### 模块结构

```
engines/similar_case_search/
├── __init__.py              # 包入口，导出公共API
├── models.py                # Pydantic 数据模型
├── keyword_extractor.py     # LLM 关键词提取
├── local_search.py          # 本地索引搜索
└── relevance_ranker.py      # LLM 相关性排序

data/
└── court_cases_index.json   # 本地案例索引（示例数据）
```

### 数据流

```
案件 YAML → keyword_extractor (LLM) → 关键词列表
                                          ↓
本地索引 JSON → local_search (关键词匹配) → 候选案例列表
                                               ↓
                                    relevance_ranker (LLM) → 排序后的类案列表
                                                                 ↓
                                                    docx_generator → 报告附录 section
```

### 核心类设计

1. **KeywordExtractor** — 接收 `LLMClient`，async `.extract(case_data) -> CaseKeywords`
2. **LocalCaseSearcher** — 纯同步，`.search(keywords) -> list[CaseIndexEntry]`，加载 JSON 索引做匹配
3. **RelevanceRanker** — 接收 `LLMClient`，async `.rank(case_data, candidates) -> list[RankedCase]`

### 报告集成

在 `docx_generator.py` 的 `generate_docx_report()` 中追加可选 section：
- 接收 `similar_cases: list[RankedCase] | None` 参数
- 非 None 时渲染"类案检索参考"section
- 用现有 `_add_run()` helper 保持风格一致

## Success Criteria

- 从案件 YAML 到类案报告 section 的端到端流程可运行
- 本地搜索在示例数据上能匹配到相关案例
- LLM 排序产出带评分和分析的结构化结果
- DOCX 报告中类案 section 格式专业

## Scope Boundaries

- 不实现网页爬虫或浏览器自动化
- 不实现索引数据的自动更新（后续通过脚本批量填充）
- 不生成独立的类案检索报告文档（集成到现有报告中）
- V3 报告系统的集成留待后续（当前 CLI 使用旧版 docx_generator）
