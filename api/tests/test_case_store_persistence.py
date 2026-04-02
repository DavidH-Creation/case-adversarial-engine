"""
Tests for CaseStore persistence: save_to_disk, load_from_disk, _record_to_meta,
evict_expired persistence, and save_to_disk call sites in run_extraction /
run_analysis.

Coverage targets (≥15 tests):
  - _record_to_meta includes materials + all required fields
  - save_to_disk: returns True/False, writes file, persists materials, overwrites
  - load_from_disk: public alias, None on missing, recovers materials
  - evict_expired: calls save_to_disk before delete, state survives on disk
  - run_extraction: save called after status=extracting and after status=failed
  - run_analysis: save called after status=analyzing, after success, after failed
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import api.service as service_module
from api.schemas import CaseStatus
from api.service import CaseRecord, CaseStore, _record_to_meta

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_CASE_INFO = {
    "case_type": "civil_loan",
    "plaintiff": {"party_id": "p-test", "name": "Test Plaintiff"},
    "defendant": {"party_id": "d-test", "name": "Test Defendant"},
    "claims": [],
    "defenses": [],
}


def _make_store(tmp_path: Path) -> CaseStore:
    return CaseStore(workspaces_dir=tmp_path / "workspaces")


# ---------------------------------------------------------------------------
# Group 1: _record_to_meta
# ---------------------------------------------------------------------------


def test_record_to_meta_includes_materials():
    """_record_to_meta must include 'materials' so submitted materials survive recovery."""
    record = CaseRecord("case-abc123", _CASE_INFO)
    record.materials = {"plaintiff": [{"text": "contract"}], "defendant": []}
    meta = _record_to_meta(record)
    assert "materials" in meta
    assert meta["materials"] == {"plaintiff": [{"text": "contract"}], "defendant": []}


def test_record_to_meta_all_required_fields():
    """_record_to_meta must include all fields needed for disk recovery."""
    record = CaseRecord("case-abc123", _CASE_INFO)
    meta = _record_to_meta(record)
    required = {"case_id", "status", "info", "materials", "analysis_data", "run_id", "error"}
    assert required.issubset(meta.keys()), f"Missing: {required - meta.keys()}"


def test_record_to_meta_status_is_string():
    """_record_to_meta must serialize status as a plain string for JSON round-trip."""
    record = CaseRecord("case-abc123", _CASE_INFO)
    meta = _record_to_meta(record)
    assert isinstance(meta["status"], str)
    assert meta["status"] == CaseStatus.created.value


# ---------------------------------------------------------------------------
# Group 2: save_to_disk
# ---------------------------------------------------------------------------


def test_save_to_disk_returns_true_when_workspace_set(tmp_path):
    """save_to_disk returns True when the record has an active workspace_manager."""
    store = _make_store(tmp_path)
    record = store.create(_CASE_INFO)
    assert store.save_to_disk(record.case_id) is True


def test_save_to_disk_returns_false_for_unknown_case_id(tmp_path):
    """save_to_disk returns False when case_id is not in the store."""
    store = _make_store(tmp_path)
    assert store.save_to_disk("case-doesnotexist") is False


def test_save_to_disk_writes_case_meta_json(tmp_path):
    """save_to_disk writes case_meta.json to the workspace directory."""
    store = _make_store(tmp_path)
    record = store.create(_CASE_INFO)
    store.save_to_disk(record.case_id)
    meta_file = tmp_path / "workspaces" / record.case_id / "case_meta.json"
    assert meta_file.exists(), "case_meta.json should exist after save_to_disk"
    meta = json.loads(meta_file.read_text())
    assert meta["case_id"] == record.case_id


def test_save_to_disk_persists_materials(tmp_path):
    """save_to_disk writes the materials field so submitted evidence survives restart."""
    store = _make_store(tmp_path)
    record = store.create(_CASE_INFO)
    record.materials = {
        "plaintiff": [{"text": "evidence doc", "source_id": "s1"}],
        "defendant": [],
    }
    store.save_to_disk(record.case_id)
    meta = json.loads(
        (tmp_path / "workspaces" / record.case_id / "case_meta.json").read_text()
    )
    assert meta["materials"]["plaintiff"][0]["text"] == "evidence doc"


def test_save_to_disk_returns_false_without_workspace(tmp_path):
    """save_to_disk returns False when the record has no workspace_manager."""
    store = CaseStore(workspaces_dir=None)
    record = CaseRecord("case-nows", _CASE_INFO)
    record.workspace_manager = None
    store._cases["case-nows"] = (record, time.time())
    assert store.save_to_disk("case-nows") is False


def test_save_to_disk_overwrites_existing_meta(tmp_path):
    """save_to_disk updates case_meta.json on subsequent calls with the latest state."""
    store = _make_store(tmp_path)
    record = store.create(_CASE_INFO)
    store.save_to_disk(record.case_id)
    # Update status and save again
    record.status = CaseStatus.extracting
    store.save_to_disk(record.case_id)
    meta = json.loads(
        (tmp_path / "workspaces" / record.case_id / "case_meta.json").read_text()
    )
    assert meta["status"] == CaseStatus.extracting.value


# ---------------------------------------------------------------------------
# Group 3: load_from_disk (public alias for _load_from_disk)
# ---------------------------------------------------------------------------


def test_load_from_disk_public_alias_recovers_saved_record(tmp_path):
    """load_from_disk is a public alias for _load_from_disk; recovers a case after restart."""
    store = _make_store(tmp_path)
    record = store.create(_CASE_INFO)
    record.status = CaseStatus.extracting
    store.save_to_disk(record.case_id)

    fresh_store = _make_store(tmp_path)
    recovered = fresh_store.load_from_disk(record.case_id)
    assert recovered is not None
    assert recovered.case_id == record.case_id


def test_load_from_disk_returns_none_for_missing_case(tmp_path):
    """load_from_disk returns None when no case_meta.json exists on disk."""
    store = _make_store(tmp_path)
    assert store.load_from_disk("case-nonexistent") is None


def test_load_from_disk_recovers_materials(tmp_path):
    """load_from_disk restores the materials field that was saved by save_to_disk."""
    store = _make_store(tmp_path)
    record = store.create(_CASE_INFO)
    record.materials = {
        "plaintiff": [{"text": "material 1", "source_id": "s1"}],
        "defendant": [],
    }
    store.save_to_disk(record.case_id)

    fresh_store = _make_store(tmp_path)
    recovered = fresh_store.load_from_disk(record.case_id)
    assert recovered is not None
    assert recovered.materials["plaintiff"][0]["text"] == "material 1"


# ---------------------------------------------------------------------------
# Group 4: evict_expired calls save_to_disk before removing
# ---------------------------------------------------------------------------


def test_evict_expired_calls_save_to_disk_before_removing(tmp_path):
    """evict_expired must call save_to_disk for each expired entry before deleting it."""
    store = _make_store(tmp_path)
    record = store.create(_CASE_INFO)
    store._ttl = -1  # Negative TTL: everything is immediately expired

    with patch.object(store, "save_to_disk", wraps=store.save_to_disk) as mock_save:
        store.evict_expired()

    mock_save.assert_called_once_with(record.case_id)


def test_evict_expired_last_state_survives_on_disk(tmp_path):
    """After eviction, the last in-memory state is readable from disk."""
    store = _make_store(tmp_path)
    record = store.create(_CASE_INFO)
    record.status = CaseStatus.extracting
    store._ttl = -1  # Negative TTL: everything is immediately expired

    count = store.evict_expired()

    assert count == 1
    assert record.case_id not in store._cases
    meta = json.loads(
        (tmp_path / "workspaces" / record.case_id / "case_meta.json").read_text()
    )
    assert meta["status"] == CaseStatus.extracting.value


# ---------------------------------------------------------------------------
# Group 5: run_extraction calls store.save_to_disk
# ---------------------------------------------------------------------------


async def test_run_extraction_saves_after_extracting_status(tmp_path):
    """run_extraction calls store.save_to_disk(case_id) after setting status=extracting."""
    from engines.shared.models import IssueTree

    test_store = _make_store(tmp_path)
    record = test_store.create(_CASE_INFO)
    record.materials = {
        "plaintiff": [
            {"text": "loan doc", "source_id": "s1", "doc_type": "contract", "role": "plaintiff"}
        ],
        "defendant": [],
    }

    save_calls: list[tuple] = []

    def capture_save(case_id):
        save_calls.append((case_id, record.status))
        return True

    with (
        patch.object(service_module, "store", test_store),
        patch.object(test_store, "save_to_disk", side_effect=capture_save),
        patch("api.service.EvidenceIndexer") as mock_indexer_cls,
        patch("api.service.IssueExtractor") as mock_extractor_cls,
        patch("api.service.ClaudeCLIClient"),
    ):
        mock_indexer = AsyncMock()
        mock_indexer.index.return_value = []
        mock_indexer_cls.return_value = mock_indexer

        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = IssueTree(
            case_id=record.case_id, issues=[], burdens=[]
        )
        mock_extractor_cls.return_value = mock_extractor

        await service_module.run_extraction(record)

    extracting_saves = [c for c in save_calls if c[1] == CaseStatus.extracting]
    assert len(extracting_saves) >= 1, (
        "save_to_disk must be called while status=extracting; calls were: "
        + str(save_calls)
    )


async def test_run_extraction_saves_after_failed(tmp_path):
    """run_extraction calls store.save_to_disk(case_id) after status=failed."""
    test_store = _make_store(tmp_path)
    record = test_store.create(_CASE_INFO)
    record.materials = {
        "plaintiff": [
            {"text": "x", "source_id": "s1", "doc_type": "contract", "role": "plaintiff"}
        ],
        "defendant": [],
    }

    save_calls: list[tuple] = []

    def capture_save(case_id):
        save_calls.append((case_id, record.status))
        return True

    with (
        patch.object(service_module, "store", test_store),
        patch.object(test_store, "save_to_disk", side_effect=capture_save),
        patch("api.service.EvidenceIndexer") as mock_indexer_cls,
        patch("api.service.ClaudeCLIClient"),
    ):
        mock_indexer = AsyncMock()
        mock_indexer.index.side_effect = RuntimeError("LLM error")
        mock_indexer_cls.return_value = mock_indexer

        await service_module.run_extraction(record)

    assert record.status == CaseStatus.failed
    failed_saves = [c for c in save_calls if c[1] == CaseStatus.failed]
    assert len(failed_saves) >= 1, (
        "save_to_disk must be called while status=failed; calls were: "
        + str(save_calls)
    )


# ---------------------------------------------------------------------------
# Group 6: run_analysis calls store.save_to_disk
# ---------------------------------------------------------------------------


async def test_run_analysis_saves_after_analyzing_status(tmp_path):
    """run_analysis calls store.save_to_disk(case_id) after setting status=analyzing."""
    from engines.adversarial.schemas import AdversarialResult
    from engines.shared.models import EvidenceIndex, IssueTree

    test_store = _make_store(tmp_path)
    record = test_store.create(_CASE_INFO)
    record.issue_tree = IssueTree(case_id=record.case_id, issues=[], burdens=[])
    record.ev_index = EvidenceIndex(case_id=record.case_id, evidence=[])

    save_calls: list[tuple] = []

    def capture_save(case_id):
        save_calls.append((case_id, record.status))
        return True

    async def fake_run_rounds(*args, **kwargs):
        return AdversarialResult(
            case_id=record.case_id,
            run_id="run-test-12345678",
            rounds=[],
            summary=None,
        )

    with (
        patch.object(service_module, "store", test_store),
        patch.object(test_store, "save_to_disk", side_effect=capture_save),
        patch("api.service._run_rounds", side_effect=fake_run_rounds),
        patch("api.service.ClaudeCLIClient"),
        patch("api.service._build_case_data_dict", return_value={}),
        patch("api.service._generate_markdown_report", return_value="md"),
    ):
        await service_module.run_analysis(record)

    analyzing_saves = [c for c in save_calls if c[1] == CaseStatus.analyzing]
    assert len(analyzing_saves) >= 1, (
        "save_to_disk must be called while status=analyzing; calls were: "
        + str(save_calls)
    )


async def test_run_analysis_saves_after_success(tmp_path):
    """run_analysis calls store.save_to_disk(case_id) after analysis completes successfully."""
    from engines.adversarial.schemas import AdversarialResult
    from engines.shared.models import EvidenceIndex, IssueTree

    test_store = _make_store(tmp_path)
    record = test_store.create(_CASE_INFO)
    record.issue_tree = IssueTree(case_id=record.case_id, issues=[], burdens=[])
    record.ev_index = EvidenceIndex(case_id=record.case_id, evidence=[])

    save_calls: list[tuple] = []

    def capture_save(case_id):
        save_calls.append((case_id, record.status))
        return True

    async def fake_run_rounds(*args, **kwargs):
        return AdversarialResult(
            case_id=record.case_id,
            run_id="run-test-12345678",
            rounds=[],
            summary=None,
        )

    with (
        patch.object(service_module, "store", test_store),
        patch.object(test_store, "save_to_disk", side_effect=capture_save),
        patch("api.service._run_rounds", side_effect=fake_run_rounds),
        patch("api.service.ClaudeCLIClient"),
        patch("api.service._build_case_data_dict", return_value={}),
        patch("api.service._generate_markdown_report", return_value="md"),
    ):
        await service_module.run_analysis(record)

    assert record.status == CaseStatus.analyzed
    analyzed_saves = [c for c in save_calls if c[1] == CaseStatus.analyzed]
    assert len(analyzed_saves) >= 1, (
        "save_to_disk must be called while status=analyzed; calls were: "
        + str(save_calls)
    )


async def test_run_analysis_saves_after_failed(tmp_path):
    """run_analysis calls store.save_to_disk(case_id) after status=failed."""
    from engines.shared.models import EvidenceIndex, IssueTree

    test_store = _make_store(tmp_path)
    record = test_store.create(_CASE_INFO)
    record.issue_tree = IssueTree(case_id=record.case_id, issues=[], burdens=[])
    record.ev_index = EvidenceIndex(case_id=record.case_id, evidence=[])

    save_calls: list[tuple] = []

    def capture_save(case_id):
        save_calls.append((case_id, record.status))
        return True

    with (
        patch.object(service_module, "store", test_store),
        patch.object(test_store, "save_to_disk", side_effect=capture_save),
        patch("api.service._run_rounds", side_effect=RuntimeError("analysis failed")),
        patch("api.service.ClaudeCLIClient"),
    ):
        await service_module.run_analysis(record)

    assert record.status == CaseStatus.failed
    failed_saves = [c for c in save_calls if c[1] == CaseStatus.failed]
    assert len(failed_saves) >= 1, (
        "save_to_disk must be called while status=failed; calls were: "
        + str(save_calls)
    )
