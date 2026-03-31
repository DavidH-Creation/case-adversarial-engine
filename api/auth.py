"""
最小化 Bearer Token 认证。
环境变量 API_SECRET_KEY 驱动：未设置时开放访问，设置后强制验证。
"""

from __future__ import annotations

import os

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """FastAPI 依赖项：验证 Bearer Token。

    - API_SECRET_KEY 未配置 → 开放访问（本地开发默认）
    - API_SECRET_KEY 已配置 → 要求 Authorization: Bearer <key>
    """
    secret = os.getenv("API_SECRET_KEY")
    if not secret:
        return  # 未配置时跳过认证
    if not credentials or credentials.credentials != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
