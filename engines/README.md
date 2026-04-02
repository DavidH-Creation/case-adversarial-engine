# Engines

这里是仓库的运行时主体，不再是 scaffold 占位目录。

## Workflow Engines

- `case_structuring/`
  材料进入系统后的结构化处理，包括证据索引、争点提取和确定性规则层。
- `procedure_setup/`
  程序配置、庭前准备、hearing order 之类的准备阶段能力。
- `simulation_run/`
  对抗推演、裁判路径、攻击链、可信度和 scenario 分析。
- `report_generation/`
  Markdown / DOCX report、executive summary 和输出层 parity。
- `interactive_followup/`
  报告后追问、drill-down 和二次解释。

## Shared Runtime

- `shared/`
  共享模型、workspace manager、access control、CLI adapter、consistency helpers、progress reporting。

## Supporting / Legacy Runtime

- `adversarial/`
  原始双边对抗引擎。
- `pretrial_conference/`
  程序化庭前会议能力。
- `case_extraction/`
  API 驱动的提取链路。
- `document_assistance/`
  文书辅助能力。
- `similar_case_search/`
  相似案例搜索能力。

这些目录都仍在当前 repo 中发挥作用，不应再被描述成“future seams”。
