# Eval And Acceptance

## 目标

本文件定义多角色案件对抗推演系统的 benchmark 组织方式、版本指标、通过标准、失败标准和不可接受回归。没有评测口径，就没有稳定迭代。

## Benchmark Dataset Organization

### 首个金标集要求

- 至少 20 个历史案件
- 当前阶段只覆盖民事 `民间借贷`
- 每案必须包含：
  - 原始材料
  - 标准争点
  - 关键证据及证据编号
  - 待证事实
  - 举证责任分配
  - 参考结论或律师备注

### 建议组织方式

每个 benchmark case 至少应包含以下逻辑结构：

- `case_manifest`
- `source_materials`
- `gold_issue_tree`
- `gold_evidence_index`
- `gold_burden_map`
- `gold_timeline`
- `lawyer_notes`

### 标注要求

- 争点、证据、结论必须能互相映射
- 关键结论必须能定位到证据编号
- 律师备注必须区分“事实判断”“推断判断”“经验建议”

## Metric Definitions

### 核心指标

- `issue_extraction_accuracy`
- `citation_completeness`
- `evidence_gap_discovery_rate`
- `run_to_run_consistency`
- `access_isolation_violations`
- `state_machine_violations`
- `job_recoverability`
- `report_followup_traceability`
- `scenario_diff_validity`
- `run_replayability`

### 指标说明

- `issue_extraction_accuracy`：系统抽取出的核心争点与金标争点的匹配度
- `citation_completeness`：关键结论中带有效 `evidence_id` 引用的比例
- `evidence_gap_discovery_rate`：系统发现且被律师评为有用的缺证点比例
- `run_to_run_consistency`：同一输入多次运行时结构化结果的一致性
- `access_isolation_violations`：越权读取、越权引用次数
- `state_machine_violations`：证据状态非法迁移、非法入轮次数
- `job_recoverability`：长任务中断后恢复与重启的可靠性
- `report_followup_traceability`：报告后追问答案继续保持证据与争点追溯的比例
- `scenario_diff_validity`：what-if 结果差异是否有清晰变更解释
- `run_replayability`：同一 `Run` 是否可重新还原输入、状态与主要输出

## Version Acceptance

## v0.5

- `issue_extraction_accuracy >= 80%`
- 每份证据都能绑定至少一个待证事实
- `citation_completeness = 100%` for 关键结论
- 报告可被律师在 5 分钟内读懂并判断是否有用

## v1

- 同一案件重复运行 5 次，争点树一致性 `>= 75%`
- 对抗后新增关键缺证点比例显著高于 `v0.5`
- 原被告输出中的关键论点全部带 `evidence_id`
- `access_isolation_violations = 0`
- `job_recoverability` 基础可用

## v1.5

- 法官追问中，70% 以上被律师评价为“确实会问”
- 证据状态机无非法迁移
- 裁判倾向必须能回溯到质证记录
- `private` 证据泄漏为零
- `report_followup_traceability` 达标

## v2

- 5 个民事案型各自通过 10 个历史案件回放
- “争点-证据-抗辩”矩阵可稳定生成
- 文书框架人工修改量明显下降
- 对象模型不因案型扩展而破坏兼容
- `scenario_diff_validity` 达标

## v2.5

- 律师能在工作台内完成“上传-结构化-推演-复核-导出”
- 审计链完整
- 常见敏感信息脱敏不漏检
- 用户级权限测试通过
- `run_replayability` 可用于案件历史回放

## v3

- 至少 30 个刑事样本案件回放
- 辩护要点与真实律师意见高重合
- 非法证据/程序瑕疵识别误报率可控
- 定罪与量刑分析链条分离清晰

## v3.5

- 能正确标识第三人及其利益位置
- 能区分实体违法和程序违法
- 能给出撤诉、变更、继续审理分流建议
- 行政依据链可追溯

## v4

- 新增案型无需重写主引擎
- 所有输出都可追溯到模板、回合、证据
- 支持历史案件批量回放评测
- 平台级 benchmark 可按案型分别评分

## v4.5

- 通过内部安全测试
- 权限穿透为零
- 每个导出结论都有律师签发位
- 租户隔离与审计导出测试通过

## v5

- 三大案种主干均可用
- 多场景推演共享同一对象模型和审计链
- 多输出全部具备证据、模板、回合追溯
- 在受控环境内形成完整办案闭环

## Pass / Fail Rules

### 通过标准

一个版本被判定为通过，必须同时满足：

- 达到该版本的全部强制指标
- 不触发任何 hard fail
- 关键输出经人工抽检可理解、可追溯、可复现

### 失败标准

出现以下任一情况，即视为版本失败：

- 核心准确率指标未达标
- 关键结论缺少 `evidence_id`
- 关键对象输出字段缺失
- 同一输入多次运行导致结构化结果不可接受漂移
- 权限隔离或证据状态机违反系统规则

## Hard Fail

以下问题一票否决：

- `private` 证据泄漏
- 无证据引用的关键结论
- `evidence_state_machine` 非法迁移
- 裁判层引用未进入 `admitted_record` 的证据
- 输出无法区分 `fact` / `inference` / `assumption`
- 审计链缺失，无法还原“谁在何时基于什么得出什么”
- 报告追问答案没有证据引用
- `Scenario` 重跑后差异无法解释
- `Run` 无法回放还原
- `Job` 状态与实际产物不一致

## Unacceptable Regression

以下 regression 不可接受，即使新增功能有效也不能合并：

- `issue_extraction_accuracy` 显著下降
- `citation_completeness` 下降
- `run_to_run_consistency` 显著下降
- 新版本引入访问隔离漏洞
- 新版本引入证据状态错乱
- 对象模型字段名被悄悄改写，导致旧 benchmark 失效

## 当前阶段评测重点

当前只聚焦 `v0.5`，优先验证：

- 争点树是否稳定
- 证据索引是否完整
- 举证责任映射是否可读
- 结构化报告是否具备备战价值
- 输出格式是否兼容未来 `CaseWorkspace`

在 `v0.5` 之前，不接受“先做功能，评测以后再补”的开发方式。
