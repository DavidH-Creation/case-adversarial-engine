from __future__ import annotations

import importlib

import pytest


eval_benchmark = importlib.import_module("scripts.eval_benchmark")


def test_compute_issue_metrics_uses_one_to_one_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eval_benchmark, "_best_match", lambda *_args, **_kwargs: 1.0)

    metrics = eval_benchmark.compute_issue_metrics(
        extracted_issues=[{"title": "通用争点"}],
        gold=[
            {"title": "争点一"},
            {"title": "争点二"},
            {"title": "争点三"},
        ],
        matcher="bigram",
    )

    assert metrics["precision_hits"] == 1
    assert metrics["recall_hits"] == 1
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == pytest.approx(1 / 3, rel=0.001)


@pytest.mark.asyncio
async def test_compare_matchers_reuses_cached_engine_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    async def _fake_eval_case(case_id: str, **kwargs) -> dict:
        calls.append({"case_id": case_id, **kwargs})
        return {
            "case_id": case_id,
            "title": f"title-{case_id}",
            "evidence_metrics": {"f1": 0.4, "recall": 0.4, "precision": 0.4},
            "issue_metrics": {"f1": 0.5, "recall": 0.5, "precision": 0.5},
        }

    monkeypatch.setattr(eval_benchmark, "eval_case", _fake_eval_case)
    monkeypatch.setattr(eval_benchmark, "_get_judge_client", lambda: "judge-bin")

    comparison = await eval_benchmark.run_matcher_comparison(
        cases=["civil-loan-001", "civil-loan-002"],
        model="claude-sonnet-4-6",
        verbose=False,
        match_only=False,
    )

    assert [call["matcher"] for call in calls] == [
        "bigram",
        "bigram",
        "llm-judge",
        "llm-judge",
    ]
    assert [call["match_only"] for call in calls] == [False, False, True, True]
    assert all(call["judge_client"] is None for call in calls[:2])
    assert all(call["judge_client"] == "judge-bin" for call in calls[2:])
    assert list(comparison.keys()) == ["bigram", "llm-judge"]
    assert len(comparison["bigram"]["results"]) == 2
    assert len(comparison["llm-judge"]["results"]) == 2
