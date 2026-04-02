# Product Roadmap

## 双轨说明

这个仓库现在按两条版本线推进：

- `Core Track = v2`
  内核、对象模型、工作流、持久化、scenario、多案型 civil kernel。
- `Output Track = v3.x`
  报告架构、Markdown / DOCX parity、导出语义、报告恢复与一致性。

不要再把 `v2` 和 `v3.x` 当成同一条单线版本历史。

## Core Track

### 已完成

| Milestone | 结果 |
|------|------|
| `v0.5` | 单案种静态结构化分析、证据索引、争点提取、基础报告 |
| `v1` | 双边对抗、访问隔离、三轮攻防、基础长任务与上下文管理 |
| `v1.2` | 争点排序、金额校验、裁判路径树、攻击链、可信度与行动建议等分析层 |
| `v1.5` | 程序化庭前会议、证据状态机、法官追问、报告后追问合同 |

### 当前目标：`v2`

`v2` 是 civil kernel，不是 report overhaul。

当前重点：

- 统一对象模型和案型插件机制
- 巩固 `CaseWorkspace` / `Run` / `Job` 的持久化和恢复语义
- 让 CLI、API、scenario 共享同一批结构化产物
- 把 `civil_loan`、`labor_dispute`、`real_estate` 放进同一条 civil kernel 里，而不是各写一套孤立流程

### Next：`v2.5`

`v2.5` 才是更偏产品层的律师工作台和律所工作流：

- 案件列表、回放、复核、导出
- 更清晰的用户级权限和审计
- 更稳定的人工复核入口

## Output Track

### 当前基线：`v3.2 on main`

`v3.2` 关注的是输出系统，不是内核版本递进。

当前已经锁定的产品决策：

- 主线输出不再包含 mediation / settlement-range 段落
- 用户可见输出不再使用概率、置信区间、`prob=` 或“可能性：”这类措辞
- Markdown 和 DOCX 走同一套主线语义
- `--resume` 可从持久化产物恢复后重新生成报告

### 下一步

`v3.x` 后续工作更偏导出与体验一致性：

- 更多 export surface 的 parity
- 报告层结构继续清理，但不再和 `Core Track` 混写成同一版本故事
- 必要时再拆 DOCX / report generation 的实现结构

## 未来扩展

这些是未来产品方向，但不再占用 `v3` 这个版本号：

### Criminal Expansion

- 刑事专线
- 控辩双方与程序要点的独立模板
- 非法证据、定罪与量刑分离分析

### Administrative Expansion

- 行政争议专线
- 合法性审查、程序违法与实体违法区分
- 第三人利益与分流建议

### Platformization

- 多案种插件平台
- 更强的批量回放评估
- 律所级部署、权限、审计与私有化能力

## 路线图使用规则

- 涉及对象模型、workflow、workspace、scenario 的变更，归 `Core Track`。
- 涉及 Markdown、DOCX、report semantics、export parity 的变更，归 `Output Track`。
- 新文档和新 PR 说明必须明确自己改的是哪条线。
