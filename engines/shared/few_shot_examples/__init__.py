"""
Few-shot examples 加载器。
Loader for few-shot examples used in LLM prompts.

设计原则 / Design principles:
- 每个模块的 example 存为独立 JSON 文件
- 文件缺失 → 返回空字符串（降级，不报错）
- 通过 <example> 标签注入 system prompt
- 控制 token：每个 example 文件不超过 ~800 tokens
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_EXAMPLES_DIR = Path(__file__).parent


def load_few_shot_text(module_name: str) -> str:
    """加载指定模块的 few-shot examples 并格式化为 prompt 文本。

    Args:
        module_name: 模块名称，对应 JSON 文件名（不含后缀）。
                     如 "adversarial_plaintiff", "issue_impact_ranker"

    Returns:
        格式化后的 few-shot example 文本（含 <example> 标签），
        如文件不存在或解析失败则返回空字符串。
    """
    path = _EXAMPLES_DIR / f"{module_name}.json"
    if not path.exists():
        logger.debug("Few-shot example 文件不存在: %s（降级为无 few-shot）", path)
        return ""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Few-shot example 加载失败 (%s): %s", path, e)
        return ""

    examples: list[dict] = data if isinstance(data, list) else [data]
    if not examples:
        return ""

    parts: list[str] = ["\n## 参考示例（few-shot examples）\n"]
    for idx, ex in enumerate(examples, start=1):
        input_summary = ex.get("input_summary", "")
        expected_output = ex.get("expected_output", {})
        output_json = json.dumps(expected_output, ensure_ascii=False, indent=2)
        parts.append(
            f'<example index="{idx}">\n'
            f"输入摘要：{input_summary}\n"
            f"期望输出：\n{output_json}\n"
            f"</example>"
        )

    return "\n".join(parts)
