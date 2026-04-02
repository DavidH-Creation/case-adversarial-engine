"""
Tests for CaseStore disk persistence.

Covers:
- save_to_disk writes to disk correctly
- load_from_disk recovers state
- _record_to_meta includes materials field
- evict_expired saves before evicting
- run_extraction persists at key status transitions
- run_analysis persists at key status transitions
- Round-trip: save then load recovers same state
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import api.service as service_module
from api.schemas import CaseStatus
from api.service import CaseRecord, CaseStore, _record_to_meta, run_analysis, run_extraction
from engines.shared.models import (
    AccessDomain,
    EvidenceIndex,
    EvidenceStatus,
    EvidenceType,
    IssueTree,
)
from engines.shared.models.analysis import Issue, IssueStatus, IssueType
from engines.shared.workspace_manager import WorkspaceManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CASE_INFO = {
    "case_type": "civil_loan",
    "plaintiff": {"party_id": "p-test", "name": "TestPlaintiff"},
    "defendant": {"party_id": "d-test", "name": "TestDefendant"},
    "claims": [],
    "defenses": [],
}


@pytest.fixture()
def tmp_store(tmp_path):
    """CaseStore backed by a temp workspaces directory."""
    return CaseStore(workspaces_dir=tmp_path / "workspaces")


@pytest.fixture()
def case_with_materials(tmp_store):
    """A CaseRecord with plaintiff materials already added."""
    record = tmp_store.create(_CASE_INFO)
    record.materials["plaintiff"].append(
        {"source_id": "src-001", "text": "loan agreement", "doc_type": "contract", "role": "plaintiff"}
    )
    record.materials["defendant"].append(
        {"source_id": "src-002", "text": "repayment receipt", "doc_type": "receipt", "role": "defendant"}
    )
    return record, tmp_store


# ---------------------------------------------------------------------------
# 1. _record_to_meta includes materials
# ---------------------------------------------------------------------------


def test_record_to_meta_includes_materials(tmp_store):
    """_record_to_meta must serialize the materials field."""
    record = tmp_store.create(_CASE_INFO)
    record.materials["plaintiff"].append({"source_id": "s1", "text": "abc", "doc_type": "x", "role": "plaintiff"})

    meta = _record_to_meta(record)

    assert "materials" in meta
    assert meta["materials"]["plaintiff"] == record.materials["plaintiff"]
    assert meta["materials"]["defendant"] == record.materials["defendant"]


def test_record_to_meta_materials_empty_by_default(tmp_store):
    record = tmp_store.create(_CASE_INFO)
    meta = _record_to_meta(record)
    assert meta["materials"] == {"plaintiff": [], "defendant": []}


# ---------------------------------------------------------------------------
# 2. save_to_disk writes to disk
# ---------------------------------------------------------------------------


def test_save_to_disk_writes_case_meta(case_with_materials):
    """save_to_disk persists case_meta.json with correct content."""
    record, store = case_with_materials
    case_id = record.case_id

    result = store.save_to_disk(case_id)

    assert result is True
    wm = WorkspaceManager(store._workspaces_dir, case_id)
    meta = wm.load_case_meta()
    assert meta is not None
    assert meta["case_id"] == case_id
    assert meta["status"] == CaseStatus.created.value
    assert len(meta["materials"]["plaintiff"]) == 1
    assert meta["materials"]["plaintiff"][0]["source_id"] == "src-001"


def test_save_to_disk_returns_false_for_unknown_case(tmp_store):
    result = tmp_store.save_to_disk("case-nonexistent")
    assert result is False


def test_save_to_disk_returns_false_without_workspace_manager(tmp_store):
    """save_to_disk returns False when record has no workspace_manager."""
    record = tmp_store.create(_CASE_INFO)
    record.workspace_manager = None

    result = tmp_store.save_to_disk(record.case_id)

    assert result is False


def test_save_to_disk_persists_status_update(tmp_store):
    """save_to_disk captures the latest status value."""
    record = tmp_store.create(_CASE_INFO)
    record.status = CaseStatus.extracting

    tmp_store.save_to_disk(record.case_id)

    wm = WorkspaceManager(tmp_store._workspaces_dir, record.case_id)
    meta = wm.load_case_meta()
    assert meta["status"] == CaseStatus.extracting.value


def test_save_to_disk_persists_error_field(tmp_store):
    record = tmp_store.create(_CASE_INFO)
    record.status = CaseStatus.failed
    record.error = "something went wrong"

    tmp_store.save_to_disk(record.case_id)

    wm = WorkspaceManager(tmp_store._workspaces_dir, record.case_id)
    meta = wm.load_case_meta()
    assert meta["error"] == "something went wrong"


# ---------------------------------------------------------------------------
# 3. load_from_disk recovers state
# ---------------------------------------------------------------------------


def test_load_from_disk_recovers_basic_state(tmp_store):
    """load_from_disk reconstructs a CaseRecord with status and info."""
    record = tmp_store.create(_CASE_INFO)
    record.status = CaseStatus.extracting
    tmp_store.save_to_disk(record.case_id)

    recovered = tmp_store.load_from_disk(record.case_id)

    assert recovered is not None
    assert recovered.case_id == record.case_id
    assert recovered.status == CaseStatus.extracting
    assert recovered.info == _CASE_INFO


def test_load_from_disk_returns_none_for_unknown(tmp_store):
    result = tmp_store.load_from_disk("case-does-not-exist")
    assert result is None


def test_load_from_disk_recovers_materials(case_with_materials):
    """load_from_disk restores submitted materials (the critical regression case)."""
    record, store = case_with_materials
    store.save_to_disk(record.case_id)

    recovered = store.load_from_disk(record.case_id)

    assert recovered is not None
    assert len(recovered.materials["plaintiff"]) == 1
    assert recovered.materials["plaintiff"][0]["source_id"] == "src-001"
    assert len(recovered.materials["defendant"]) == 1


# ---------------------------------------------------------------------------
# 4. Round-trip: save then load recovers same state
# ---------------------------------------------------------------------------


def test_round_trip_save_load(tmp_store):
    """A save followed by load returns a record that matches the original."""
    record = tmp_store.create(_CASE_INFO)
    record.status = CaseStatus.extracted
    record.materials["plaintiff"].append({"source_id": "rt-src", "text": "roundtrip", "doc_type": "x", "role": "plaintiff"})
    record.error = None
    record.run_id = None

    tmp_store.save_to_disk(record.case_id)
    recovered = tmp_store.load_from_disk(record.case_id)

    assert recovered is not None
    assert recovered.case_id == record.case_id
    assert recovered.status == record.status
    assert recovered.info == record.info
    assert recovered.materials == record.materials
    assert recovered.error == record.error


def test_round_trip_preserves_analysis_data(tmp_store):
    """analysis_data survives a save/load cycle via load_from_disk."""
    record = tmp_store.create(_CASE_INFO)
    record.status = CaseStatus.analyzed
    record.analysis_data = {"run_id": "run-abc", "overall_assessment": "Plaintiff prevails"}
    record.run_id = "run-abc"

    tmp_store.save_to_disk(record.case_id)
    recovered = tmp_store.load_from_disk(record.case_id)

    assert recovered is not None
    assert recovered.analysis_data == record.analysis_data
    assert recovered.run_id == "run-abc"


# ---------------------------------------------------------------------------
# 5. evict_expired saves before evicting
# ---------------------------------------------------------------------------


def test_evict_expired_saves_before_eviction(tmp_store):
    """evict_expired must flush to disk before removing from memory."""
    record = tmp_store.create(_CASE_INFO)
    record.status = CaseStatus.analyzing
    record.materials["plaintiff"].append({"source_id": "evict-src", "text": "evict test", "doc_type": "x", "role": "plaintiff"})
    case_id = record.case_id

    # Force immediate expiry by back-dating the entry
    with tmp_store._lock:
        tmp_store._cases[case_id] = (record, time.time() - tmp_store._ttl - 1)

    count = tmp_store.evict_expired()

    assert count == 1
    # Case should no longer be in memory
    assert tmp_store._cases.get(case_id) is None
    assert case_id in tmp_store._evicted

    # But it should have been saved to disk before removal
    wm = WorkspaceManager(tmp_store._workspaces_dir, case_id)
    meta = wm.load_case_meta()
    assert meta is not None
    assert meta["status"] == CaseStatus.analyzing.value
    assert len(meta["materials"]["plaintiff"]) == 1


def test_evict_expired_adds_to_evicted_set(tmp_store):
    """After eviction, case_id is in _evicted so disk fallback is skipped."""
    record = tmp_store.create(_CASE_INFO)
    case_id = record.case_id
    with tmp_store._lock:
        tmp_store._cases[case_id] = (record, time.time() - tmp_store._ttl - 1)

    tmp_store.evict_expired()

    assert case_id in tmp_store._evicted
    # get() must return None (not fall back to disk) for evicted cases
    assert tmp_store.get(case_id) is None


# ---------------------------------------------------------------------------
# 6. run_extraction persists at key transitions
# ---------------------------------------------------------------------------


def test_run_extraction_saves_on_extracting_status(tmp_path):
    """run_extraction calls save_to_disk immediately after setting status=extracting."""
    test_store = CaseStore(workspaces_dir=tmp_path / "workspaces")
    record = test_store.create(_CASE_INFO)
    record.materials["plaintiff"].append(
        {"source_id": "ex-src", "text": "test material", "doc_type": "contract", "role": "plaintiff"}
    )
    case_id = record.case_id

    saved_statuses: list[str] = []

    original_save = test_store.save_to_disk

    def tracking_save(cid: str) -> bool:
        result = original_save(cid)
        entry = test_store._cases.get(cid)
        if entry:
            saved_statuses.append(entry[0].status.value)
        return result

    with patch.object(service_module, "store", test_store):
        # Patch the indexer and extractor to raise immediately so we can
        # inspect what was saved before the error path
        with patch("api.service.EvidenceIndexer") as mock_idx_cls:
            mock_idx = AsyncMock()
            mock_idx.index = AsyncMock(side_effect=RuntimeError("abort"))
            mock_idx_cls.return_value = mock_idx

            with patch.object(test_store, "save_to_disk", side_effect=tracking_save):
                asyncio.run(run_extraction(record))

    assert CaseStatus.extracting.value in saved_statuses


def test_run_extraction_saves_on_failure(tmp_path):
    """run_extraction calls save_to_disk after setting status=failed."""
    test_store = CaseStore(workspaces_dir=tmp_path / "workspaces")
    record = test_store.create(_CASE_INFO)
    record.materials["plaintiff"].append(
        {"source_id": "ex-src", "text": "test", "doc_type": "contract", "role": "plaintiff"}
    )

    save_calls: list[str] = []

    def tracking_save(cid: str) -> bool:
        r = test_store._cases.get(cid)
        if r:
            save_calls.append(r[0].status.value)
        return True

    with patch.object(service_module, "store", test_store):
        with patch("api.service.EvidenceIndexer") as mock_cls:
            mock_idx = AsyncMock()
            mock_idx.index = AsyncMock(side_effect=ValueError("index error"))
            mock_cls.return_value = mock_idx

            with patch.object(test_store, "save_to_disk", side_effect=tracking_save):
                asyncio.run(run_extraction(record))

    assert record.status == CaseStatus.failed
    assert CaseStatus.failed.value in save_calls


# ---------------------------------------------------------------------------
# 7. run_analysis persists at key transitions
# ---------------------------------------------------------------------------


def _make_minimal_adversarial_result(case_id: str):
    """Build an AdversarialResult with no rounds for analysis testing."""
    from engines.adversarial.schemas import AdversarialResult

    return AdversarialResult(case_id=case_id, run_id="run-test-001", rounds=[])


def _make_ev_index(case_id: str) -> EvidenceIndex:
    from engines.shared.models import Evidence

    ev = Evidence(
        evidence_id="ev-test-001",
        case_id=case_id,
        owner_party_id="p-test",
        title="Test evidence",
        source="src-001",
        summary="Test summary",
        evidence_type=EvidenceType.documentary,
        target_fact_ids=["fact-test-001"],
        status=EvidenceStatus.private,
        access_domain=AccessDomain.owner_private,
    )
    return EvidenceIndex(case_id=case_id, evidence=[ev])


def _make_issue_tree(case_id: str) -> IssueTree:
    issue = Issue(
        issue_id="issue-test-001",
        case_id=case_id,
        title="Test issue",
        description="Test",
        issue_type=IssueType.legal,
        status=IssueStatus.open,
    )
    return IssueTree(case_id=case_id, issues=[issue], burdens=[])


def test_run_analysis_saves_on_analyzing_status(tmp_path):
    """run_analysis calls save_to_disk after setting status=analyzing."""
    test_store = CaseStore(workspaces_dir=tmp_path / "workspaces")
    record = test_store.create(_CASE_INFO)
    record.ev_index = _make_ev_index(record.case_id)
    record.issue_tree = _make_issue_tree(record.case_id)
    record.status = CaseStatus.extracted

    saved_statuses: list[str] = []
    original_save = test_store.save_to_disk

    def tracking_save(cid: str) -> bool:
        r = test_store._cases.get(cid)
        if r:
            saved_statuses.append(r[0].status.value)
        return original_save(cid)

    mock_result = _make_minimal_adversarial_result(record.case_id)

    with patch.object(service_module, "store", test_store):
        with patch("api.service._run_rounds", AsyncMock(return_value=mock_result)):
            with patch("api.service._generate_markdown_report", return_value="# Report"):
                with patch.object(test_store, "save_to_disk", side_effect=tracking_save):
                    asyncio.run(run_analysis(record))

    assert CaseStatus.analyzing.value in saved_statuses


def test_run_analysis_saves_on_success(tmp_path):
    """run_analysis calls save_to_disk after status=analyzed."""
    test_store = CaseStore(workspaces_dir=tmp_path / "workspaces")
    record = test_store.create(_CASE_INFO)
    record.ev_index = _make_ev_index(record.case_id)
    record.issue_tree = _make_issue_tree(record.case_id)
    record.status = CaseStatus.extracted

    saved_statuses: list[str] = []
    original_save = test_store.save_to_disk

    def tracking_save(cid: str) -> bool:
        r = test_store._cases.get(cid)
        if r:
            saved_statuses.append(r[0].status.value)
        return original_save(cid)

    mock_result = _make_minimal_adversarial_result(record.case_id)

    with patch.object(service_module, "store", test_store):
        with patch("api.service._run_rounds", AsyncMock(return_value=mock_result)):
            with patch("api.service._generate_markdown_report", return_value="# Report"):
                with patch.object(test_store, "save_to_disk", side_effect=tracking_save):
                    asyncio.run(run_analysis(record))

    assert record.status == CaseStatus.analyzed
    assert CaseStatus.analyzed.value in saved_statuses


def test_run_analysis_saves_on_failure(tmp_path):
    """run_analysis calls save_to_disk after status=failed."""
    test_store = CaseStore(workspaces_dir=tmp_path / "workspaces")
    record = test_store.create(_CASE_INFO)
    record.ev_index = _make_ev_index(record.case_id)
    record.issue_tree = _make_issue_tree(record.case_id)
    record.status = CaseStatus.extracted

    saved_statuses: list[str] = []

    def tracking_save(cid: str) -> bool:
        r = test_store._cases.get(cid)
        if r:
            saved_statuses.append(r[0].status.value)
        return True

    with patch.object(service_module, "store", test_store):
        with patch("api.service._run_rounds", AsyncMock(side_effect=RuntimeError("analysis boom"))):
            with patch.object(test_store, "save_to_disk", side_effect=tracking_save):
                asyncio.run(run_analysis(record))

    assert record.status == CaseStatus.failed
    assert CaseStatus.failed.value in saved_statuses
