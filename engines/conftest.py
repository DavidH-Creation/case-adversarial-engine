"""
engines/ 层 pytest 配置。
Patch engines.shared.llm_utils._sleep to a no-op coroutine so retry backoff
does not add real wall-clock time to the test suite.
"""

import asyncio
import pytest


@pytest.fixture(autouse=True)
def _no_llm_retry_sleep(monkeypatch):
    """替换 LLM 重试退避中的 sleep 为即时返回，加速测试。
    Replace retry backoff sleep with instant no-op to keep tests fast.
    """

    async def _instant_sleep(_delay: float) -> None:  # noqa: RUF029
        await asyncio.sleep(0)

    monkeypatch.setattr("engines.shared.llm_utils._sleep", _instant_sleep)
