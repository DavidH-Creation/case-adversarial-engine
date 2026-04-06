"""Tests for engines/shared/event_log.py — append-only JSONL event log."""

import json
import threading

import pytest


def test_append_and_load(tmp_path):
    from engines.shared.event_log import CaseEvent, EventLog, EventType

    log = EventLog(tmp_path, "case-test")
    e1 = CaseEvent(case_id="case-test", event_type=EventType.case_created)
    e2 = CaseEvent(case_id="case-test", event_type=EventType.analysis_done)
    log.append(e1)
    log.append(e2)
    events = log.load_all()
    assert len(events) == 2
    assert events[0].event_type == EventType.case_created
    assert events[1].event_type == EventType.analysis_done


def test_append_is_additive_across_instances(tmp_path):
    from engines.shared.event_log import CaseEvent, EventLog, EventType

    log1 = EventLog(tmp_path, "case-test")
    log2 = EventLog(tmp_path, "case-test")
    log1.append(CaseEvent(case_id="case-test", event_type=EventType.case_created))
    log2.append(CaseEvent(case_id="case-test", event_type=EventType.confirmed))
    assert len(EventLog(tmp_path, "case-test").load_all()) == 2


def test_load_since_returns_events_after_marker(tmp_path):
    from engines.shared.event_log import CaseEvent, EventLog, EventType

    log = EventLog(tmp_path, "case-test")
    e1 = CaseEvent(case_id="case-test", event_type=EventType.case_created)
    e2 = CaseEvent(case_id="case-test", event_type=EventType.extraction_started)
    e3 = CaseEvent(case_id="case-test", event_type=EventType.extraction_done)
    log.append(e1)
    log.append(e2)
    log.append(e3)

    after = log.load_since(e1.event_id)
    assert len(after) == 2
    assert after[0].event_id == e2.event_id
    assert after[1].event_id == e3.event_id


def test_load_since_unknown_id_returns_all(tmp_path):
    from engines.shared.event_log import CaseEvent, EventLog, EventType

    log = EventLog(tmp_path, "case-test")
    log.append(CaseEvent(case_id="case-test", event_type=EventType.case_created))
    # Unknown marker → return all events
    events = log.load_since("evt-doesnotexist")
    assert len(events) == 1


def test_load_all_empty_file(tmp_path):
    from engines.shared.event_log import EventLog

    log = EventLog(tmp_path, "case-empty")
    assert log.load_all() == []


def test_concurrent_append_no_data_loss(tmp_path):
    from engines.shared.event_log import CaseEvent, EventLog, EventType

    N = 50
    log = EventLog(tmp_path, "case-concurrent")

    def worker(i: int):
        log.append(
            CaseEvent(
                case_id="case-concurrent",
                event_type=EventType.material_added,
                payload={"i": i},
            )
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    events = EventLog(tmp_path, "case-concurrent").load_all()
    assert len(events) == N


def test_event_fields_roundtrip(tmp_path):
    """Verify all CaseEvent fields survive JSONL serialization."""
    from engines.shared.event_log import CaseEvent, EventLog, EventType

    log = EventLog(tmp_path, "case-rt")
    original = CaseEvent(
        case_id="case-rt",
        event_type=EventType.analysis_done,
        actor_id="user-abc",
        payload={"run_id": "run-xyz"},
    )
    log.append(original)
    loaded = log.load_all()[0]
    assert loaded.event_id == original.event_id
    assert loaded.case_id == original.case_id
    assert loaded.event_type == original.event_type
    assert loaded.actor_id == original.actor_id
    assert loaded.payload == original.payload
    assert loaded.created_at == original.created_at
