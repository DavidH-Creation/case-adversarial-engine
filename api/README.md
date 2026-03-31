# API 文档

案件对抗分析系统 REST API（`api/app.py`）。

## 启动

```bash
cd <project_root>
uvicorn api.app:app --reload --port 8000
```

交互式文档：`http://localhost:8000/docs`

## 认证

| 配置 | 行为 |
|------|------|
| `API_SECRET_KEY` 未设置 | 开放访问（本地开发默认） |
| `API_SECRET_KEY=<secret>` | 所有端点要求 `Authorization: Bearer <secret>` |

```bash
export API_SECRET_KEY="my-secret-token"
curl -H "Authorization: Bearer my-secret-token" http://localhost:8000/api/cases/
```

## 主要端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/cases/` | 创建案件，返回 `case_id` |
| `POST` | `/api/cases/{case_id}/materials` | 上传案件材料 |
| `POST` | `/api/cases/{case_id}/extract` | 触发证据提取 + 争点识别 |
| `GET` | `/api/cases/{case_id}/extraction` (SSE) | 流式获取提取进度 |
| `POST` | `/api/cases/{case_id}/confirm` | 确认争点，进入分析阶段 |
| `POST` | `/api/cases/{case_id}/analyze` | 触发三轮对抗分析 |
| `GET` | `/api/cases/{case_id}/analysis` (SSE) | 流式获取分析进度 |
| `GET` | `/api/cases/{case_id}/artifacts` | 列出分析产物文件 |
| `GET` | `/api/cases/{case_id}/artifacts/{name}` | 获取具体产物 JSON |
| `GET` | `/api/cases/{case_id}/report/markdown` | 获取 Markdown 分析报告 |
| `POST` | `/api/cases/{case_id}/scenarios/run` | 运行情景假设分析 |
| `GET` | `/api/cases/{case_id}/scenarios/{scenario_id}` | 获取情景分析结果 |

## SSE 重连说明

分析完成后，SSE 客户端重连时会先回放完整的历史进度消息，再退出流。无需担心错过已完成状态。

## 持久化

`CaseRecord` 通过 `WorkspaceManager` 持久化到磁盘（`workspaces/api/<case_id>/`）。
服务重启后可通过 `CaseStore.load_from_workspace(case_id)` 恢复案件状态。

内存中的 `CaseStore` 设有 24h TTL，过期后自动清理防止内存泄漏。

## 与 WorkspaceManager 的关系

API 层通过 `_WORKSPACE_BASE`（默认 `<project_root>/workspaces/api`）初始化工作空间。
设置环境变量 `WORKSPACE_BASE` 可覆盖默认路径。测试中可将 `api.service._WORKSPACE_BASE = None` 禁用持久化。
