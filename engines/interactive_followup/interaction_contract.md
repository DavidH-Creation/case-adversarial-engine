# 交互追问合同 (Interactive Followup Contract)

## 概述
交互追问引擎支持律师在报告生成后对特定争点或结论进行深入追问，每轮追问保持完整的证据和争点追溯链。

## 输入
| 字段 | 类型 | 说明 |
|------|------|------|
| report | ReportArtifact | 已生成的报告，须符合 report_artifact.schema.json |
| question | string | 用户追问问题 |
| previous_turns | InteractionTurn[] | 之前的追问轮次（可选，用于多轮追问上下文） |

## 输出
产物为 InteractionTurn 对象，须符合 `interaction_turn.schema.json`。

## 约束规则
1. **证据边界**：回答不能引用未在报告上下文中出现的证据（evidence_ids 必须是报告已引用证据的子集）
2. **争点关联**：每轮追问必须绑定至少一个 issue_id
3. **陈述分类**：回答必须标注 statement_class
4. **追溯完整**：answer 中的每个事实性断言必须有对应的 evidence_id
5. **上下文一致**：多轮追问中，后续回答不得与之前轮次的事实性陈述矛盾

## 不含
- 聊天 UI / 前端界面
- 会话记忆系统
- 社交仿真 / 角色扮演
- 追问不产生独立 Run

## 运行方式
- 追问产物登记到 CaseWorkspace.artifact_index.InteractionTurn
- 不产生独立 Run，挂在原报告的 Run 下
- 合同层不限制追问轮数

## 验收标准
- 零证据边界违反（不引用报告外证据）
- 零悬空 issue_id 引用
- 100% 陈述分类覆盖
- 多轮追问无事实矛盾