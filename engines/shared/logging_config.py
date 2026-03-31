"""
结构化日志配置 — StructuredLogger wrapper，输出 JSON 格式日志。
Structured logging configuration — StructuredLogger wrapper with JSON output.

提供:
- JsonFormatter: 将 logging.LogRecord 格式化为 JSON 行
- TokenTracker: 聚合全 pipeline 的 LLM token 用量
- setup_pipeline_logging(): 初始化 JSON 日志到文件 + stderr
- LLMCallRecord: 单次 LLM 调用的结构化记录

用法 / Usage::

    from engines.shared.logging_config import setup_pipeline_logging, get_token_tracker

    setup_pipeline_logging(log_file=Path("outputs/run/pipeline.log"))
    # ... run pipeline ...
    summary = get_token_tracker().summary()
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# LLM call record
# ---------------------------------------------------------------------------


@dataclass
class LLMCallRecord:
    """单次 LLM 调用的结构化记录 / Structured record for a single LLM call."""

    timestamp: str
    module: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float
    success: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# Token tracker
# ---------------------------------------------------------------------------


# 粗估费率（USD per 1M tokens）— 仅供参考，随 API 价格变动需更新
# Rough cost rates (USD per 1M tokens) — for reference only
_COST_PER_1M_INPUT = 3.0
_COST_PER_1M_OUTPUT = 15.0


class TokenTracker:
    """聚合全 pipeline 的 LLM token 用量 / Aggregates LLM token usage across the pipeline."""

    def __init__(self) -> None:
        self._records: list[LLMCallRecord] = []

    @property
    def records(self) -> list[LLMCallRecord]:
        return list(self._records)

    def record(self, rec: LLMCallRecord) -> None:
        """记录一次 LLM 调用 / Record a single LLM call."""
        self._records.append(rec)

    def summary(self) -> dict[str, Any]:
        """返回 token 用量汇总 / Return token usage summary.

        Returns::

            {
                "total_input_tokens": int,
                "total_output_tokens": int,
                "total_cost_estimate": float,
                "total_calls": int,
                "per_module_breakdown": {
                    "module_name": {
                        "input_tokens": int,
                        "output_tokens": int,
                        "calls": int,
                        "errors": int,
                    }
                },
            }
        """
        total_input = sum(r.input_tokens for r in self._records if r.input_tokens is not None)
        total_output = sum(r.output_tokens for r in self._records if r.output_tokens is not None)

        per_module: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.module not in per_module:
                per_module[r.module] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "calls": 0,
                    "errors": 0,
                }
            m = per_module[r.module]
            m["calls"] += 1
            if r.input_tokens is not None:
                m["input_tokens"] += r.input_tokens
            if r.output_tokens is not None:
                m["output_tokens"] += r.output_tokens
            if not r.success:
                m["errors"] += 1

        cost = (total_input / 1_000_000 * _COST_PER_1M_INPUT) + (
            total_output / 1_000_000 * _COST_PER_1M_OUTPUT
        )

        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_estimate": round(cost, 4),
            "total_calls": len(self._records),
            "per_module_breakdown": per_module,
        }


# ---------------------------------------------------------------------------
# Global tracker instance
# ---------------------------------------------------------------------------

_token_tracker = TokenTracker()


def get_token_tracker() -> TokenTracker:
    """获取全局 TokenTracker 实例 / Get the global TokenTracker instance."""
    return _token_tracker


def reset_token_tracker() -> None:
    """重置全局 TokenTracker（用于测试或新 pipeline）/ Reset global tracker."""
    global _token_tracker  # noqa: PLW0603
    _token_tracker = TokenTracker()


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """将 logging.LogRecord 格式化为 JSON 行 / Formats LogRecord as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # LLM 调用记录附加字段 / Attach LLM call record if present
        llm_call: LLMCallRecord | None = getattr(record, "llm_call", None)
        if llm_call is not None:
            entry["llm_call"] = asdict(llm_call)
        return json.dumps(entry, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Setup function
# ---------------------------------------------------------------------------


def setup_pipeline_logging(
    log_file: Path | None = None,
    level: int = logging.INFO,
) -> None:
    """初始化结构化 JSON 日志，输出到文件和 stderr。
    Initialize structured JSON logging to file and stderr.

    Args:
        log_file: JSON 日志文件路径（None 则仅输出到 stderr）/ Path for JSON log file.
        level:    日志级别 / Log level (default INFO).
    """
    root = logging.getLogger()
    json_fmt = JsonFormatter()

    # stderr handler — JSON 格式
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(json_fmt)
    stderr_handler.setLevel(level)

    # 避免重复添加 handler / Avoid duplicate handlers
    # 移除已有的 StructuredLogger handlers（通过自定义属性标记）
    for h in root.handlers[:]:
        if getattr(h, "_structured_pipeline", False):
            root.removeHandler(h)

    stderr_handler._structured_pipeline = True  # type: ignore[attr-defined]
    root.addHandler(stderr_handler)

    # 文件 handler / File handler
    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_file), mode="w", encoding="utf-8")
            file_handler.setFormatter(json_fmt)
            file_handler.setLevel(level)
            file_handler._structured_pipeline = True  # type: ignore[attr-defined]
            root.addHandler(file_handler)
        except OSError:
            # 日志文件写入失败时不中断主 pipeline
            # Don't break the pipeline if log file creation fails
            logging.getLogger(__name__).warning(
                "Failed to create log file: %s", log_file, exc_info=True
            )

    root.setLevel(min(root.level, level) if root.level != logging.WARNING else level)
