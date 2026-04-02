# API

FastAPI 服务入口在 `api/app.py`。

## Run

```bash
uvicorn api.app:app --reload --port 8000
```

交互式文档默认在 `http://localhost:8000/docs`。

## Auth

| Config | Behavior |
|------|------|
| `API_SECRET_KEY` 未设置 | 本地开发默认开放访问 |
| `API_SECRET_KEY=<secret>` | 所有端点要求 `Authorization: Bearer <secret>` |

## Main Flow

### Case lifecycle

| Method | Path | Purpose |
|------|------|------|
| `POST` | `/api/cases/` | 创建案件，返回 `case_id` |
| `POST` | `/api/cases/{case_id}/materials` | 上传材料 |
| `POST` | `/api/cases/{case_id}/extract` | 启动提取任务 |
| `GET` | `/api/cases/{case_id}/extraction` | 读取提取结果，提取中返回 `202` |
| `POST` | `/api/cases/{case_id}/confirm` | 确认或编辑提取后的争点 |
| `POST` | `/api/cases/{case_id}/analyze` | 启动分析任务 |
| `GET` | `/api/cases/{case_id}/analysis` | SSE 分析进度流 |

### Report and artifacts

| Method | Path | Purpose |
|------|------|------|
| `GET` | `/api/cases/{case_id}/artifacts` | 列出当前案件可见产物 |
| `GET` | `/api/cases/{case_id}/artifacts/{artifact_name}` | 读取单个产物 |
| `GET` | `/api/cases/{case_id}/report/markdown` | 读取 Markdown report |
| `GET` | `/api/cases/{case_id}/report` | 下载 DOCX report |

### Scenario

| Method | Path | Purpose |
|------|------|------|
| `POST` | `/api/scenarios/run` | 基于 baseline `run_id` 运行 scenario |
| `GET` | `/api/scenarios/{scenario_id}` | 读取 scenario diff |

## Runtime Semantics

### Single-flight behavior

- 同一 `case_id` 上重复 `POST /extract` 不会再启动第二个提取任务
- 同一 `case_id` 上重复 `POST /analyze` 不会再启动第二个分析任务
- 当任务已在运行中时，接口继续返回 `202`，但语义是幂等重入，不是重复开跑

### SSE behavior

`GET /api/cases/{case_id}/analysis` 的行为是：

- 分析进行中时，先回放一次当前历史进度，再继续推送实时进度
- 分析完成后重连，直接返回一次 `done`
- 分析失败时，返回结构化 `error`

### Persistence and recovery

API workspace 默认位于 `workspaces/api/<case_id>/`。

当前恢复语义包括：

- 重启后可恢复案件状态
- `artifacts` 列表可恢复
- Markdown report 可恢复
- DOCX report 可恢复
- scenario 基于 baseline metadata 读取真实 `case_type`

## Notes

- API 层的目标不是重新实现 CLI，而是给案件式、可恢复、可重连的运行面提供服务化入口。
- 当前详细运行语义以 `api/app.py` 和 `api/service.py` 为准。
