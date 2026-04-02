# case-adversarial-engine

多角色案件对抗推演系统 / Multi-role adversarial case simulation engine

## What This Repo Is

这是一个面向中国诉讼备战场景的案件分析引擎仓库。

它不做“法院一定会怎么判”的承诺。它做的是把案件材料结构化、把争点和证据关系拉平、把程序状态和访问边界固定下来，再在这个约束下跑对抗推演、报告生成和 `what-if` 场景比较。

当前仓库同时承载两条版本线：

| Track | 关注点 | 当前状态 |
|------|------|------|
| `Core Track = v2` | 内核、对象模型、五阶段工作流、案型扩展、workspace 持久化、scenario | 当前主线，继续演进 |
| `Output Track = v3.2` | 报告架构、Markdown / DOCX parity、导出语义 | 已在 `main` 落地，主线输出已去 mediation、去 probability |

## Entry Points

### CLI

```bash
python scripts/run_case.py cases/wang_v_chen_zhuang_2025.yaml
python scripts/run_case.py cases/my_case.yaml --model claude-sonnet-4-6
python scripts/run_case.py cases/my_case.yaml --resume
```

### API

```bash
uvicorn api.app:app --reload --port 8000
```

交互式文档默认在 `http://localhost:8000/docs`。

## Main Outputs

CLI 运行默认写入 `outputs/<timestamp>/`，当前主线会生成这些产物：

```text
outputs/<timestamp>/
  result.json
  report.md
  report.docx
  decision_tree.json
  executive_summary.json
  attack_chain.json
  amount_report.json
```

API 路径另外会把案件状态和可恢复产物持久化到 `workspaces/api/<case_id>/`，服务重启后仍可恢复 `artifacts`、Markdown report 和 DOCX report。

## What This Repo Is Not

- 不是 AI 法官
- 不是面向 C 端用户的法律咨询产品
- 不是自动向法院提交材料的系统
- 不是无证据追溯的聊天式 demo
- 不是绕过律师复核直接出正式法律意见的自动化工具

## Documentation

- 当前有效文档入口：[docs/README.md](docs/README.md)
- 仓库结构总览：[docs/05_repository_map.md](docs/05_repository_map.md)
- 历史档案入口：[docs/archive/README.md](docs/archive/README.md)

建议先读：

1. [docs/00_north_star.md](docs/00_north_star.md)
2. [docs/02_architecture.md](docs/02_architecture.md)
3. [docs/03_case_object_model.md](docs/03_case_object_model.md)
4. [docs/01_product_roadmap.md](docs/01_product_roadmap.md)
5. [docs/04_eval_and_acceptance.md](docs/04_eval_and_acceptance.md)

## Repo Pointers

- `scripts/`：CLI 入口和辅助脚本
- `api/`：FastAPI 服务和 API persistence orchestration
- `engines/`：五阶段工作流引擎和共享运行时
- `schemas/`：JSON Schema 契约
- `benchmarks/`：金标集、fixtures、acceptance 参考
- `tests/`：单元、集成、API 和 smoke 测试
- `docs/archive/`：历史计划、评审和设计资料

## Design Priorities

- `schema stability`
- `workspace-backed persistence`
- `citation traceability`
- `access isolation`
- `replayability`
- `versioned evaluation`
