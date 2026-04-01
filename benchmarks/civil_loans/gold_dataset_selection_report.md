# Gold Dataset Selection Report

## Overview

- **Total cases selected**: 20
- **Case type**: 民间借贷 (Civil Loan Disputes)
- **Source**: `data/court_cases_index.json` (94 loan-related cases from 5226 total)
- **Selection criteria**: Summary richness, legal issue diversity, court level variety
- **Annotation method**: Dual-agent cross-verification (Agent A + Agent B independent annotation, then merge)
- **Date**: 2026-04-01

## Selection Methodology

1. Filtered `court_cases_index.json` for cases with `cause_of_action` containing "借贷" or "借款合同"
2. Scored each case by summary length and presence of priority legal topics
3. Selected top 20 ensuring topic diversity across categories

### Topic Coverage

| Category | Cases |
|----------|-------|
| 担保/保证 (Guarantee) | 001, 002, 003, 004, 005, 007, 009, 011 |
| 借新还旧 (Refinancing) | 001, 005 |
| 行为能力 (Capacity) | 002 |
| 债务加入/转移 (Debt Assumption) | 003 |
| 刑民交叉 (Criminal-Civil Intersection) | 004 |
| 利息/砍头息 (Interest/Deducted Principal) | 006, 010 |
| 不良信用记录 (Credit Records) | 007 |
| 抵销权 (Set-off) | 008 |
| 公司对外担保 (Corporate Guarantee) | 009 |
| 非典型保证 (Atypical Guarantee) | 011 |
| 主体资格 (Standing) | 012 |
| 清算/破产 (Liquidation) | 013 |
| 一人公司/人格否认 (Veil Piercing) | 014 |
| 清算不能 (Failure to Liquidate) | 015 |
| 债权转让/管辖 (Assignment/Jurisdiction) | 016, 017, 020 |
| 表见代理 (Apparent Authority) | 018 |
| 借贷事实认定 (Loan Fact Verification) | 019 |

### Court Level Distribution

| Court Level | Count | Cases |
|-------------|-------|-------|
| 最高人民法院 | 5 | 002, 004, 010, 012, 020 |
| 省高级人民法院 | 4 | 001, 005, 008, 019 |
| 中级人民法院 | 4 | 003, 013, 014, 015 |
| 基层人民法院 | 5 | 006, 007, 009, 016, 017 |
| 专门法院 | 1 | 011 (海事法院) |
| 成渝金融法院等 | 1 | 018 |

## Case List

| # | Case ID | Case Number | Court | Key Topic |
|---|---------|-------------|-------|-----------|
| 1 | civil-loan-001 | （2018）苏民再316号 | 江苏省高级人民法院 | 借新还旧中保证人责任 |
| 2 | civil-loan-002 | （2020）最高法民终881号 | 最高人民法院 | 限制行为能力人担保效力 |
| 3 | civil-loan-003 | （2019）粤52民终421号 | 广东省揭阳市中级人民法院 | 债务加入vs债务转移 |
| 4 | civil-loan-004 | （2021）最高法民终654号 | 最高人民法院 | 应收账款质押与刑民交叉 |
| 5 | civil-loan-005 | （2022）赣民再114号 | 江西省高级人民法院 | 农信社股金质押效力 |
| 6 | civil-loan-006 | （2014）长民二（商）初字第2459号 | 上海市长宁区人民法院 | 砍头息认定 |
| 7 | civil-loan-007 | （2022）豫1727民初2523号 | 汝南县人民法院 | 保证期间与不良信用记录 |
| 8 | civil-loan-008 | （2020）鄂民终147号 | 湖北省高级人民法院 | 抵销权行使与上诉利益 |
| 9 | civil-loan-009 | （2021）京0102民初7664号 | 北京市西城区人民法院 | 公司对外担保审查义务 |
| 10 | civil-loan-010 | （2021）最高法民申1140号 | 最高人民法院 | 变相高利（服务费等）认定 |
| 11 | civil-loan-011 | （2020）鲁72民初2175号 | 青岛海事法院 | 非典型保证/增信措施 |
| 12 | civil-loan-012 | （2021）最高法民再37号 | 最高人民法院 | 原告主体资格审查 |
| 13 | civil-loan-013 | （2023）闽01民再76号 | 福建省福州市中级人民法院 | 公司清算中债权人权利 |
| 14 | civil-loan-014 | （2020）京02民再151号 | 北京市第二中级人民法院 | 一人公司财产混同 |
| 15 | civil-loan-015 | （2021）鲁03民终2919号 | 山东省淄博市中级人民法院 | 清算不能连带责任 |
| 16 | civil-loan-016 | （2019）沪0107民初13686号 | 上海市普陀区人民法院 | 债权转让后合同履行地 |
| 17 | civil-loan-017 | （2024）沪0107民初8524号 | 上海市普陀区人民法院 | 预先约定协议管辖效力 |
| 18 | civil-loan-018 | （2021）鄂02民终2246号 | 湖北省黄石市中级人民法院 | 表见代理认定 |
| 19 | civil-loan-019 | （1998）琼高法民终字第8号 | 海南省高级人民法院 | 借贷事实认定/借条证明力 |
| 20 | civil-loan-020 | （2019）最高法民终506号 | 最高人民法院 | 诉讼中债权转让通知 |

## Annotation Structure (per case)

Each case directory contains:

```
benchmarks/civil_loans/{case_id}/
  case_manifest.json          ← 案件元数据
  gold_issue_tree.json        ← 金标争点树
  gold_evidence_index.json    ← 金标证据索引
  gold_burden_map.json        ← 金标举证责任分配
  lawyer_notes.json           ← 律师备注（事实/推断/经验建议）
  source_materials/           ← 原始材料目录（仅结构，无全文）
```

## Dual-Agent Cross-Verification Protocol

1. **Independent annotation**: Two agents independently annotate the same case
2. **Cross-verification**: Compare issue trees, evidence indices, and burden maps
3. **Merge rules**:
   - Both annotated consistently → confirmed directly
   - One agent more detailed → adopt richer version
   - Disagreement → review against case summary and legal principles, select more accurate version
4. **Final output**: Merged, validated JSON files saved as gold standard

## Completion Statistics

| Metric | Count |
|--------|-------|
| Total cases annotated | 20/20 |
| JSON validation pass rate | 100% |
| Total issues | 105 |
| Total evidence items | 146 |
| Total burden mappings | 108 |
| Total lawyer notes | 119 |
| Average issues per case | 5.2 |
| Average evidence per case | 7.3 |
| Average burdens per case | 5.4 |
| Average notes per case | 6.0 |

### Issue Type Distribution

| Type | Count | Percentage |
|------|-------|------------|
| legal | 56 | 53% |
| factual | 21 | 20% |
| mixed | 18 | 17% |
| procedural | 10 | 10% |

### Note Class Distribution

| Class | Count | Percentage |
|-------|-------|------------|
| experience_advice | 45 | 38% |
| fact | 41 | 34% |
| inference | 33 | 28% |

### Per-Case Breakdown

| # | Case ID | Parties | Issues | Evidence | Burdens | Notes |
|---|---------|---------|--------|----------|---------|-------|
| 001 | civil-loan-001 | 3 | 6 | 9 | 6 | 5 |
| 002 | civil-loan-002 | 3 | 7 | 10 | 9 | 8 |
| 003 | civil-loan-003 | 4 | 5 | 6 | 6 | 7 |
| 004 | civil-loan-004 | 3 | 5 | 7 | 5 | 7 |
| 005 | civil-loan-005 | 3 | 5 | 9 | 5 | 7 |
| 006 | civil-loan-006 | 2 | 5 | 7 | 5 | 8 |
| 007 | civil-loan-007 | 3 | 6 | 7 | 6 | 8 |
| 008 | civil-loan-008 | 2 | 5 | 9 | 5 | 5 |
| 009 | civil-loan-009 | 3 | 5 | 8 | 5 | 5 |
| 010 | civil-loan-010 | 2 | 5 | 6 | 5 | 7 |
| 011 | civil-loan-011 | 3 | 5 | 7 | 5 | 5 |
| 012 | civil-loan-012 | 2 | 5 | 6 | 5 | 5 |
| 013 | civil-loan-013 | 2 | 5 | 7 | 5 | 5 |
| 014 | civil-loan-014 | 3 | 6 | 7 | 5 | 5 |
| 015 | civil-loan-015 | 4 | 6 | 9 | 6 | 5 |
| 016 | civil-loan-016 | 3 | 5 | 6 | 5 | 7 |
| 017 | civil-loan-017 | 2 | 4 | 6 | 4 | 5 |
| 018 | civil-loan-018 | 3 | 5 | 7 | 6 | 5 |
| 019 | civil-loan-019 | 2 | 5 | 6 | 5 | 5 |
| 020 | civil-loan-020 | 3 | 5 | 7 | 5 | 5 |

## Data Limitations

- Annotations are based on case summaries (裁判要旨), not full case texts
- Evidence items are inferred from the summary (what documents would exist in such a case)
- Actual case materials are not available; source_materials/ directories are structural placeholders
- Complexity levels may be underestimated due to summary compression
