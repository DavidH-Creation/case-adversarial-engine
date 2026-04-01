"""Tests for Evidence Battle Matrix and Evidence Classifier."""

import pytest
from unittest.mock import MagicMock
from enum import Enum

from engines.report_generation.v3.evidence_classifier import (
    classify_evidence_risk,
    classify_all_evidence,
)
from engines.report_generation.v3.models import EvidenceRiskLevel


class MockEvidenceType(str, Enum):
    documentary = "documentary"
    electronic_data = "electronic_data"
    audio_visual = "audio_visual"
    witness_statement = "witness_statement"
    other = "other"


def _make_evidence(
    evidence_id="EV001",
    title="Test Evidence",
    evidence_type=MockEvidenceType.documentary,
    source="银行流水",
    is_copy_only=False,
    challenged_by_party_ids=None,
    admissibility_score=1.0,
    owner_party_id="party-p",
    target_fact_ids=None,
    target_issue_ids=None,
    summary="Test summary",
    status=None,
):
    ev = MagicMock()
    ev.evidence_id = evidence_id
    ev.title = title
    ev.evidence_type = evidence_type
    ev.source = source
    ev.is_copy_only = is_copy_only
    ev.challenged_by_party_ids = challenged_by_party_ids or []
    ev.admissibility_score = admissibility_score
    ev.owner_party_id = owner_party_id
    ev.target_fact_ids = target_fact_ids or []
    ev.target_issue_ids = target_issue_ids or []
    ev.summary = summary
    ev.status = status or MagicMock(value="submitted")
    return ev


class TestClassifyEvidenceRisk:
    def test_bank_record_is_green(self):
        result = classify_evidence_risk(
            "EV001", "银行转账记录", "documentary", "银行流水"
        )
        assert result.risk_level == EvidenceRiskLevel.green

    def test_wechat_screenshot_is_yellow(self):
        result = classify_evidence_risk(
            "EV002", "微信聊天截图", "electronic_data", "微信"
        )
        assert result.risk_level == EvidenceRiskLevel.yellow

    def test_audio_recording_is_red(self):
        result = classify_evidence_risk(
            "EV003", "通话录音", "audio_visual", "手机录音"
        )
        assert result.risk_level == EvidenceRiskLevel.red

    def test_copy_only_is_red(self):
        result = classify_evidence_risk(
            "EV004", "合同复印件", "documentary", "复印件",
            is_copy_only=True,
        )
        assert result.risk_level == EvidenceRiskLevel.red

    def test_challenged_low_admissibility_is_red(self):
        result = classify_evidence_risk(
            "EV005", "争议证据", "other", "unknown",
            is_challenged=True,
            admissibility_score=0.3,
        )
        assert result.risk_level == EvidenceRiskLevel.red

    def test_very_low_admissibility_is_red(self):
        result = classify_evidence_risk(
            "EV006", "低可采性", "documentary", "unknown",
            admissibility_score=0.2,
        )
        assert result.risk_level == EvidenceRiskLevel.red

    def test_notary_source_is_green(self):
        result = classify_evidence_risk(
            "EV007", "公证书", "other", "公证处"
        )
        assert result.risk_level == EvidenceRiskLevel.green

    def test_unknown_defaults_to_yellow(self):
        result = classify_evidence_risk(
            "EV008", "其他证据", "other", "其他来源"
        )
        assert result.risk_level == EvidenceRiskLevel.yellow


class TestClassifyAllEvidence:
    def test_multiple_evidence(self):
        evidence_list = [
            _make_evidence("EV001", "银行转账", MockEvidenceType.documentary, "银行"),
            _make_evidence("EV002", "微信截图", MockEvidenceType.electronic_data, "微信"),
            _make_evidence("EV003", "录音", MockEvidenceType.audio_visual, "手机"),
        ]
        results = classify_all_evidence(evidence_list)
        assert len(results) == 3
        assert results[0].risk_level == EvidenceRiskLevel.green
        assert results[1].risk_level == EvidenceRiskLevel.yellow
        assert results[2].risk_level == EvidenceRiskLevel.red
