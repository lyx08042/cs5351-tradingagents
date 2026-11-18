"""Offline tests for the E audit module (FR-005 / INV-005 / NFR-003/004/005).

Deterministic, standard-library only, no network, no real LLM, no real trading.
Each test uses its own temporary SQLite file. Test docstrings reference the
requirement anchors they exercise.
"""
from __future__ import annotations

import ast
import copy
import json
import os
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tradingagents.course.audit import (
    AuditError,
    AuditStore,
    canonical_json,
    payload_ref,
    replay_record,
    replay_run,
    verify_against_trusted_head,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PKG_DIR = REPO_ROOT / "tradingagents" / "course" / "audit"
COURSE_DIR = REPO_ROOT / "tradingagents" / "course"

TS = "2026-11-14T17:00:00+08:00"
RULES = "v1"


def _open(tmp_path: Path, name: str = "audit.sqlite") -> AuditStore:
    return AuditStore.open(str(tmp_path / name))


def _append(store: AuditStore, record_id: str, *, run_id: str = "r-1", entry_type: str = "decision",
            payload=None, supersedes=None, rules_version: str = RULES, timestamp: str = TS):
    return store.append(
        record_id=record_id,
        run_id=run_id,
        timestamp=timestamp,
        entry_type=entry_type,
        payload={"value": 1} if payload is None else payload,
        rules_version=rules_version,
        supersedes=supersedes,
    )


def _market_gate(inputs: dict) -> dict:
    ok = inputs.get("available", 0) >= inputs.get("required", 1)
    return {
        "decision": "proceed" if ok else "abstain",
        "insufficient_domains": [] if ok else ["market"],
        "labels": inputs.get("labels", {}),
        "reason": "sufficient" if ok else "insufficient",
        "violations": [],
        "analysis_cutoff": inputs.get("analysis_cutoff"),
    }


def _safety_gate(inputs: dict) -> dict:
    accepted = inputs.get("units", 0) > 0 or inputs.get("is_noop", False)
    return {
        "accepted": accepted,
        "reason_code": None if accepted else "invalid_units",
        "status": "accepted" if accepted else "rejected",
        "action": inputs.get("action"),
        "rule_version": inputs.get("rule_version", RULES),
        "snapshot_id": inputs.get("snapshot_id"),
        "instrument": inputs.get("instrument"),
        "is_noop": inputs.get("is_noop", False),
        "ignored_claims": [],
    }


def _registry() -> dict:
    return {
        "market": {RULES: _market_gate},
        "safety": {RULES: _safety_gate},
    }


def _append_gate(store: AuditStore, record_id: str, gate_id: str, inputs: dict, observed: dict,
                 *, run_id: str = "r-1", entry_type: str = "rejection", rules_version: str = RULES,
                 payload_version=None) -> None:
    payload = {
        "gate_id": gate_id,
        "rules_version": rules_version if payload_version is None else payload_version,
        "inputs": inputs,
        "observed": observed,
        "outcome": "gate",
    }
    store.append(
        record_id=record_id,
        run_id=run_id,
        timestamp=TS,
        entry_type=entry_type,
        payload=payload,
        rules_version=rules_version,
    )


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_p01_append_initial_decision(tmp_path):
    """FR-005: store generates refs/links/hash; record is retrievable unchanged."""
    with _open(tmp_path) as store:
        rec = _append(store, "d-001", payload={"action": "hold"})
        assert rec.record_id == "d-001"
        assert rec.previous_record_id is None
        assert rec.previous_hash is None
        assert rec.payload_ref.startswith("sha256:")
        assert len(rec.record_hash) == 64
        fetched = store.get("d-001")
        assert fetched is not None
        assert fetched.to_dict() == rec.to_dict()


@pytest.mark.unit
def test_p02_reopen_preserves_records_and_triggers(tmp_path):
    """FR-005: reopening the same file keeps records and UPDATE/DELETE stay blocked."""
    path = tmp_path / "audit.sqlite"
    with AuditStore.open(str(path)) as store:
        _append(store, "d-001", payload={"x": 1})
        _append(store, "d-002", entry_type="abstain", payload={"x": 2})
    with AuditStore.open(str(path)) as store:
        assert [r.record_id for r in store.iter_run("r-1")] == ["d-001", "d-002"]
        raw = sqlite3.connect(str(path))
        try:
            with pytest.raises(sqlite3.DatabaseError):
                raw.execute("UPDATE audit_records SET payload = 'x' WHERE record_id = 'd-001'")
                raw.commit()
        finally:
            raw.close()
        with pytest.raises(sqlite3.DatabaseError):
            store._conn.execute("DELETE FROM audit_records")


@pytest.mark.unit
def test_p03_events_searchable_and_review_semantics(tmp_path):
    """NFR-004: decision + rejection(outcome=review) + abstain are searchable."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"action": "buy"})
        _append(store, "rej-1", entry_type="rejection", payload={"outcome": "review", "reason": "ambiguous"})
        _append(store, "abs-1", entry_type="abstain", payload={"reason": "no_data"})
        records = store.iter_run("r-1")
        assert [r.record_id for r in records] == ["d-001", "rej-1", "abs-1"]
        rejected = next(r for r in records if r.record_id == "rej-1")
        assert rejected.entry_type == "rejection"
        assert rejected.payload["outcome"] == "review"


@pytest.mark.unit
def test_p04_to_dict_deep_copy_isolated(tmp_path):
    """INV-005: mutating a to_dict()/payload copy cannot change the record."""
    with _open(tmp_path) as store:
        rec = _append(store, "d-001", payload={"nested": {"k": [1, 2]}})
        exported = rec.to_dict()
        exported["payload"]["nested"]["k"].append(999)
        assert rec.payload["nested"]["k"] == [1, 2]
        again = rec.to_dict()
        assert again["payload"]["nested"]["k"] == [1, 2]


@pytest.mark.unit
def test_p04b_record_is_immutable(tmp_path):
    """INV-005: AuditRecord rejects attribute set/delete and nested payload mutation."""
    with _open(tmp_path) as store:
        rec = _append(store, "d-001", payload={"nested": {"k": [1, 2]}})
        with pytest.raises(AttributeError):
            rec.record_id = "changed"
        with pytest.raises(AttributeError):
            rec.run_id = "changed-run"
        with pytest.raises(AttributeError):
            del rec.record_id
        # nested payload copy is isolated from the record
        nested = rec.payload
        nested["nested"]["k"].append(999)
        assert rec.payload["nested"]["k"] == [1, 2]
        assert rec.record_id == "d-001"


@pytest.mark.unit
def test_p05_fields_and_entry_types(tmp_path):
    """FR-005: returned record exposes task fields plus extras; entry_type validated."""
    with _open(tmp_path) as store:
        rec = _append(store, "d-001")
        d = rec.to_dict()
        for key in (
            "record_id", "run_id", "timestamp", "entry_type", "payload_ref",
            "rules_version", "previous_record_id", "payload", "previous_hash",
            "record_hash", "supersedes",
        ):
            assert key in d
        with pytest.raises(AuditError) as exc:
            _append(store, "bad", entry_type="review")
        assert exc.value.code == "invalid_entry_type"


@pytest.mark.unit
def test_p06_valid_revision_succeeds(tmp_path):
    """FR-005: a revision that supersedes the terminal decision is appended."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        rev = _append(store, "rev-1", entry_type="revision", payload={"action": "buy"}, supersedes="d-001")
        assert rev.supersedes == "d-001"


@pytest.mark.unit
def test_p07_revision_chain_keeps_old_rows(tmp_path):
    """INV-005: old rows remain; superseded_by derived; final_decision is the leaf."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        _append(store, "rev-1", entry_type="revision", payload={"action": "buy"}, supersedes="d-001")
        _append(store, "rev-2", entry_type="revision", payload={"action": "sell"}, supersedes="rev-1")
        assert store.get("d-001") is not None
        projection = store.project("r-1")
        by_id = {item["record_id"]: item for item in projection["records"]}
        assert by_id["d-001"]["superseded_by"] == "rev-1"
        assert by_id["rev-1"]["superseded_by"] == "rev-2"
        assert by_id["rev-2"]["superseded_by"] is None
        assert store.final_decision("r-1").record_id == "rev-2"


@pytest.mark.unit
def test_p08_deterministic_replay(tmp_path):
    """NFR-003: same inputs and rules version replay identically twice."""
    with _open(tmp_path) as store:
        inputs = {"available": 2, "required": 1, "labels": {"market": "available"}, "analysis_cutoff": "2026-11-13"}
        _append_gate(store, "g-1", "market", inputs, _market_gate(copy.deepcopy(inputs)))
        rec = store.get("g-1")
        first = replay_record(rec, _registry())
        second = replay_record(rec, _registry())
        assert first.status == "pass"
        assert second.status == "pass"


@pytest.mark.unit
def test_p09_trusted_head_match(tmp_path):
    """FR-005: an unchanged chain matches the captured trusted head."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        head = store.head()
        result = verify_against_trusted_head(store, head)
        assert result.ok and result.reason == "ok"


@pytest.mark.unit
def test_p10_events_after_decision_leave_trace(tmp_path):
    """NFR-004: rejection/abstain after a decision are recorded and do not change the final."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"action": "buy"})
        _append(store, "rej-1", entry_type="rejection", payload={"reason": "x"})
        _append(store, "abs-1", entry_type="abstain", payload={"reason": "y"})
        assert store.final_decision("r-1").record_id == "d-001"


@pytest.mark.unit
def test_p11_legit_append_causes_head_mismatch_not_tamper(tmp_path):
    """FR-005: a legitimate append changes the head -> head_mismatch review, not tamper."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        captured = store.head()
        _append(store, "abs-1", entry_type="abstain", payload={"reason": "later"})
        result = verify_against_trusted_head(store, captured)
        assert not result.ok
        assert result.reason == "head_mismatch"


@pytest.mark.unit
def test_p09b_head_and_verified_records_single_snapshot(tmp_path):
    """FR-005: head count equals the snapshot length; final uses the verified snapshot."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        _append(store, "rev-1", entry_type="revision", payload={"x": 1}, supersedes="d-001")
        _append(store, "abs-1", entry_type="abstain", payload={"x": 2})
        head = store.head()
        snapshot = store.verified_records()
        assert head["count"] == len(snapshot)
        assert head["record_id"] == snapshot[-1].record_id
        final = store.final_decision("r-1")
        assert final.record_id == "rev-1"


@pytest.mark.unit
def test_p12_global_chain_across_runs(tmp_path):
    """FR-005: one global chain, sequence-ordered predecessors, run filtering works."""
    with _open(tmp_path) as store:
        _append(store, "a1", run_id="r-1")
        _append(store, "b1", run_id="r-2")
        _append(store, "a2", run_id="r-1", entry_type="abstain", payload={"x": 2})
        _append(store, "b2", run_id="r-2", entry_type="rejection", payload={"x": 3})
        assert store.verify_chain().ok
        all_records = store.iter_run("r-1") + store.iter_run("r-2")
        ordered = sorted(all_records, key=lambda r: r.sequence)
        assert [r.record_id for r in ordered] == ["a1", "b1", "a2", "b2"]
        prev = None
        for rec in ordered:
            if prev is None:
                assert rec.previous_record_id is None
            else:
                assert rec.previous_record_id == prev.record_id
                assert rec.previous_hash == prev.record_hash
            prev = rec
        assert [r.record_id for r in store.iter_run("r-1")] == ["a1", "a2"]
        assert [r.record_id for r in store.iter_run("r-2")] == ["b1", "b2"]


@pytest.mark.unit
def test_p13_standalone_demo_runs(tmp_path):
    """NFR-005/FR-005: `python -S -m audit --demo` runs with cwd in tradingagents/course."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, "-S", "-m", "audit", "--demo"],
        cwd=str(COURSE_DIR),
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["all_expected"] is True


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_n01_overwrite_terminal_decision_rejected(tmp_path):
    """INV-005: a second initial decision for the same run is rejected; only one stored."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        with pytest.raises(AuditError) as exc:
            _append(store, "d-002")
        assert exc.value.code == "duplicate_decision"
        decisions = [r for r in store.iter_run("r-1") if r.entry_type == "decision"]
        assert len(decisions) == 1


@pytest.mark.unit
def test_n02_delete_history_rejected(tmp_path):
    """INV-005: DELETE on history raises via trigger and the row remains."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        with pytest.raises(sqlite3.DatabaseError):
            store._conn.execute("DELETE FROM audit_records WHERE record_id = 'd-001'")
        assert store.get("d-001") is not None


@pytest.mark.unit
def test_n03_update_history_rejected(tmp_path):
    """INV-005: UPDATE on history raises via trigger and content is unchanged."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        with pytest.raises(sqlite3.DatabaseError):
            store._conn.execute("UPDATE audit_records SET payload='{}' WHERE record_id='d-001'")
        assert store.get("d-001").payload == {"v": 1}


@pytest.mark.unit
def test_n04_duplicate_record_id_rejected(tmp_path):
    """FR-005: a duplicate record_id is rejected and the first row is kept."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        with pytest.raises(AuditError) as exc:
            _append(store, "d-001", entry_type="abstain", payload={"v": 2})
        assert exc.value.code == "duplicate_record_id"
        assert store.get("d-001").payload == {"v": 1}


@pytest.mark.unit
def test_n05_concurrent_initial_decision_race(tmp_path):
    """INV-005: two real connections race to create the first decision; exactly one wins."""
    path = str(tmp_path / "audit.sqlite")
    with _open(tmp_path) as store:
        _append(store, "seed", run_id="seed-run")
        _append(store, "seed2", run_id="seed-run", entry_type="abstain", payload={"x": 1})

    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def worker(record_id: str) -> None:
        conn = AuditStore.open(path)
        try:
            barrier.wait(timeout=10)
            conn.append(
                record_id=record_id, run_id="race-run", timestamp=TS,
                entry_type="decision", payload={"by": record_id}, rules_version=RULES,
            )
            with lock:
                results.append("ok")
        except AuditError as exc:
            with lock:
                results.append(exc.code)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, rid) for rid in ("race-a", "race-b")]
        for fut in futures:
            fut.result(timeout=30)

    assert results.count("ok") == 1
    assert any(code in ("duplicate_decision",) for code in results)
    with _open(tmp_path) as store:
        decisions = [r for r in store.iter_run("race-run") if r.entry_type == "decision"]
        assert len(decisions) == 1


@pytest.mark.unit
def test_n06_concurrent_revision_race(tmp_path):
    """INV-005: two connections revising the same terminal: at most one wins, single leaf."""
    path = str(tmp_path / "audit.sqlite")
    with _open(tmp_path) as store:
        _append(store, "dec", run_id="rev-run")
        _append(store, "seed", run_id="rev-run", entry_type="abstain", payload={"x": 1})

    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def worker(record_id: str) -> None:
        conn = AuditStore.open(path)
        try:
            barrier.wait(timeout=10)
            conn.append(
                record_id=record_id, run_id="rev-run", timestamp=TS,
                entry_type="revision", payload={"by": record_id}, rules_version=RULES,
                supersedes="dec",
            )
            with lock:
                results.append("ok")
        except AuditError as exc:
            with lock:
                results.append(exc.code)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, rid) for rid in ("rev-a", "rev-b")]
        for fut in futures:
            fut.result(timeout=30)

    assert results.count("ok") == 1
    assert "invalid_supersede" in results
    with _open(tmp_path) as store:
        assert store.verify_chain().ok
        assert store.final_decision("rev-run").record_id in ("rev-a", "rev-b")
        terminals = [
            r for r in store.iter_run("rev-run")
            if r.entry_type in ("decision", "revision")
            and all(r.record_id != other.supersedes for other in store.iter_run("rev-run"))
        ]
        assert len(terminals) == 1


@pytest.mark.unit
def test_n07_cross_run_revision_rejected(tmp_path):
    """INV-005: revision may not supersede a terminal from another run."""
    with _open(tmp_path) as store:
        _append(store, "a-dec", run_id="r-1")
        _append(store, "b-dec", run_id="r-2")
        with pytest.raises(AuditError) as exc:
            _append(store, "rev", run_id="r-2", entry_type="revision", payload={"x": 1}, supersedes="a-dec")
        assert exc.value.code == "invalid_supersede"


@pytest.mark.unit
def test_n08_old_head_revision_rejected(tmp_path):
    """INV-005: revision may not supersede an already-superseded (old) head."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        _append(store, "rev-1", entry_type="revision", payload={"x": 1}, supersedes="d-001")
        with pytest.raises(AuditError) as exc:
            _append(store, "rev-2", entry_type="revision", payload={"x": 2}, supersedes="d-001")
        assert exc.value.code == "invalid_supersede"


@pytest.mark.unit
def test_n09_event_missing_null_supersede_rejected(tmp_path):
    """INV-005: revision to an event, to a missing id, or with null supersedes is rejected."""
    with _open(tmp_path) as store:
        _append(store, "d-001")
        _append(store, "rej-1", entry_type="rejection", payload={"reason": "x"})
        with pytest.raises(AuditError) as exc:
            _append(store, "rev-1", entry_type="revision", payload={"x": 1}, supersedes="rej-1")
        assert exc.value.code == "invalid_supersede"
        with pytest.raises(AuditError) as exc:
            _append(store, "rev-2", entry_type="revision", payload={"x": 2}, supersedes="missing")
        assert exc.value.code == "invalid_supersede"
        with pytest.raises(AuditError) as exc:
            _append(store, "rev-3", entry_type="revision", payload={"x": 3}, supersedes=None)
        assert exc.value.code == "invalid_supersede"


@pytest.mark.unit
def test_n10_real_midtransaction_rollback(tmp_path):
    """INV-005: a failure occurring *inside* the transaction rolls back with no partial row.

    Uses a controlled BEFORE INSERT trigger that aborts, so the failure happens
    during INSERT rather than in write-time validation.
    """
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        before = store.head()["count"]
        store._conn.execute(
            """
            CREATE TRIGGER test_abort_insert
            BEFORE INSERT ON audit_records
            WHEN NEW.record_id = 'explode'
            BEGIN
                SELECT RAISE(ABORT, 'forced mid-transaction failure');
            END;
            """
        )
        with pytest.raises(sqlite3.DatabaseError):
            store.append(
                record_id="explode", run_id="r-1", timestamp=TS,
                entry_type="abstain", payload={"v": 2}, rules_version=RULES,
            )
        after = store.head()["count"]
        assert before == after
        assert store.get("explode") is None


@pytest.mark.unit
def test_n11_non_string_key_rejected(tmp_path):
    """NV: non-string JSON keys are rejected before any write and not coerced."""
    with _open(tmp_path) as store:
        with pytest.raises(AuditError) as exc:
            _append(store, "d-001", payload={1: "x"})
        assert exc.value.code == "non_string_key"
        assert store.get("d-001") is None


@pytest.mark.unit
def test_n12_non_finite_number_rejected(tmp_path):
    """NV: NaN/Infinity are rejected before any write."""
    with _open(tmp_path) as store:
        for bad in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(AuditError) as exc:
                _append(store, "d-001", payload={"x": bad})
            assert exc.value.code == "non_finite_number"
        assert store.get("d-001") is None


@pytest.mark.unit
def test_n12b_tuple_and_cycle_rejected(tmp_path):
    """NV: tuples and cyclic structures are rejected, not silently converted."""
    with _open(tmp_path) as store:
        with pytest.raises(AuditError) as exc:
            _append(store, "d-001", payload={"x": (1, 2)})
        assert exc.value.code == "invalid_json"
        cyclic: dict = {}
        cyclic["self"] = cyclic
        with pytest.raises(AuditError) as exc:
            _append(store, "d-001", payload=cyclic)
        assert exc.value.code == "invalid_json"
        assert store.get("d-001") is None


@pytest.mark.unit
def test_n12c_canonical_json_surrogate_rejected():
    """NV: a lone unicode surrogate raises AuditError(invalid_json), not UnicodeEncodeError."""
    with pytest.raises(AuditError) as exc:
        canonical_json({"x": "\ud800"})
    assert exc.value.code == "invalid_json"


@pytest.mark.unit
def test_n12d_canonical_json_deep_nesting_rejected():
    """NV: excessive nesting raises AuditError(invalid_json), not RecursionError."""
    deep: object = []
    node = deep
    for _ in range(5000):
        child: list = []
        node.append(child)  # type: ignore[attr-defined]
        node = child
    with pytest.raises(AuditError) as exc:
        canonical_json(deep)
    assert exc.value.code == "invalid_json"


@pytest.mark.unit
def test_n13_invalid_timestamp_and_empty_id(tmp_path):
    """NV: timestamps need a tz offset; empty ids are rejected."""
    with _open(tmp_path) as store:
        with pytest.raises(AuditError) as exc:
            _append(store, "d-001", timestamp="2026-11-14T17:00:00")
        assert exc.value.code == "invalid_timestamp"
        with pytest.raises(AuditError) as exc:
            _append(store, "d-001", timestamp="not-a-date")
        assert exc.value.code == "invalid_timestamp"
        with pytest.raises(AuditError) as exc:
            _append(store, "")
        assert exc.value.code == "empty_id"


@pytest.mark.unit
def test_n14_unknown_version_review(tmp_path):
    """NFR-003: an unknown rules_version yields review."""
    with _open(tmp_path) as store:
        _append_gate(store, "g-1", "market", {"available": 1, "required": 1}, {"decision": "proceed"},
                     rules_version="v9")
        result = replay_record(store.get("g-1"), _registry())
        assert result.status == "review"
        assert result.reason == "version_unknown"


@pytest.mark.unit
def test_n15_missing_keys_review(tmp_path):
    """FR-005: missing inputs/observed/gate_id yields review."""
    with _open(tmp_path) as store:
        _append(store, "g-1", entry_type="rejection", payload={"gate_id": "market", "rules_version": RULES, "observed": {}})
        assert replay_record(store.get("g-1"), _registry()).status == "review"
        _append(store, "g-2", entry_type="rejection", payload={"gate_id": "", "rules_version": RULES, "inputs": {}, "observed": {}})
        assert replay_record(store.get("g-2"), _registry()).reason == "missing_key"
        # Has replay fields (inputs/observed) but no gate_id: gate intent, so review.
        _append(store, "g-3", entry_type="rejection", payload={"rules_version": RULES, "inputs": {}, "observed": {}})
        g3 = replay_record(store.get("g-3"), _registry())
        assert g3.status == "review"
        assert g3.reason == "missing_key"


@pytest.mark.unit
def test_n15b_pure_narrative_inconclusive(tmp_path):
    """FR-005: a pure narrative record (no replay fields) stays inconclusive with count 0."""
    with _open(tmp_path) as store:
        _append(store, "n-1", entry_type="abstain", payload={"action": "hold", "outcome": "note", "note": "narrative"})
        result = replay_record(store.get("n-1"), _registry())
        assert result.status == "inconclusive"
        assert result.count == 0


@pytest.mark.unit
def test_n15c_mixed_valid_and_missing_gateid_run_reviews(tmp_path):
    """FR-005: a valid gate plus a gate-missing-gate_id payload reviews with gate_total=2."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-ok", "market", inputs, _market_gate(dict(inputs)))
        _append(store, "g-broken", entry_type="rejection",
                payload={"inputs": {}, "observed": {}})
        run = replay_run(store, "r-1", _registry())
        assert run.status == "review"
        assert run.gate_total == 2


@pytest.mark.unit
def test_n15d_payload_ref_mismatch_review(tmp_path):
    """FR-005: a stored payload_ref that does not match the payload yields review."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, _market_gate(dict(inputs)))
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute("UPDATE audit_records SET payload_ref = 'sha256:deadbeef' WHERE record_id='g-1'")
        result = replay_record(store.get("g-1"), _registry())
        assert result.status == "review"
        assert result.reason == "payload_ref_mismatch"


@pytest.mark.unit
def test_n16_callback_error_review(tmp_path):
    """NFR-003: a callback exception yields review, never pass."""
    def broken(_inputs):
        raise RuntimeError("boom")

    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, _market_gate(dict(inputs)))
        registry = {"market": {RULES: broken}}
        result = replay_record(store.get("g-1"), registry)
        assert result.status == "review"
        assert result.reason == "callback_error"


@pytest.mark.unit
def test_n17_rules_version_mismatch_review(tmp_path):
    """FR-005: payload.rules_version differing from the record rules_version yields review."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, _market_gate(dict(inputs)), payload_version="v2")
        result = replay_record(store.get("g-1"), _registry())
        assert result.status == "review"
        assert result.reason == "rules_version_mismatch"


@pytest.mark.unit
def test_n18_callback_mutating_input_review(tmp_path):
    """NFR-003: a callback that mutates its input copy is detected -> review."""
    def mutating(inputs):
        inputs["available"] = 999
        return {"decision": "proceed"}

    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, {"decision": "proceed"})
        result = replay_record(store.get("g-1"), {"market": {RULES: mutating}})
        assert result.status == "review"
        assert result.reason == "input_tampered"


@pytest.mark.unit
def test_n19_non_json_callback_result_review(tmp_path):
    """NFR-003: a non-JSON callback result yields review."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, {"decision": "proceed"})
        result = replay_record(store.get("g-1"), {"market": {RULES: lambda _i: object()}})
        assert result.status == "review"
        assert result.reason == "non_json_result"


@pytest.mark.unit
def test_n19b_surrogate_callback_result_review(tmp_path):
    """NFR-003: a callback result with a lone surrogate reviews, no UnicodeEncodeError leak."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, {"decision": "proceed"})
        result = replay_record(store.get("g-1"), {"market": {RULES: lambda _i: {"bad": "\ud800"}}})
        assert result.status == "review"
        assert result.reason == "non_json_result"


@pytest.mark.unit
def test_n19c_replay_malformed_json_record_review(tmp_path):
    """NV: a record read from a row with invalid JSON payload reviews, no exception escapes."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, _market_gate(dict(inputs)))
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute("UPDATE audit_records SET payload = 'broken-json' WHERE record_id='g-1'")
        record = store.get("g-1")  # materialises the raw broken payload text
        result = replay_record(record, _registry())
        assert result.status == "review"


@pytest.mark.unit
def test_n20_tampered_payload_detected(tmp_path):
    """INV-005: directly editing stored payload text is detected by verify_chain."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute(
            "UPDATE audit_records SET payload = ? WHERE record_id = 'd-001'",
            (json.dumps({"v": 999}, sort_keys=True, separators=(",", ":")),),
        )
        result = store.verify_chain()
        assert not result.ok
        assert result.reason == "payload_tampered"


@pytest.mark.unit
def test_n21_tampered_hash_detected(tmp_path):
    """INV-005: a modified record_hash / previous_hash is reported as broken."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        _append(store, "d-002", entry_type="abstain", payload={"v": 2})
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute("UPDATE audit_records SET record_hash = 'deadbeef' WHERE record_id='d-002'")
        result = store.verify_chain()
        assert not result.ok
        assert result.reason == "chain_broken"


@pytest.mark.unit
def test_n21b_malformed_json_payload_no_escape(tmp_path):
    """INV-005/FR-005: a non-JSON payload does not escape as JSONDecodeError.

    verify_chain returns a false VerificationResult, replay_run reviews with no
    callbacks, authoritative reads raise chain_broken, and append refuses.
    """
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute(
            "UPDATE audit_records SET payload = 'broken-json' WHERE record_id = 'd-001'"
        )
        result = store.verify_chain()
        assert not result.ok
        assert result.reason == "malformed_payload"

        calls = {"n": 0}

        def never(_inputs):
            calls["n"] += 1
            return {}

        run = replay_run(store, "r-1", {"market": {RULES: never}})
        assert run.status == "review"
        assert run.results == []
        assert calls["n"] == 0

        with pytest.raises(AuditError) as exc:
            store.final_decision("r-1")
        assert exc.value.code == "chain_broken"
        with pytest.raises(AuditError) as exc:
            store.project("r-1")
        assert exc.value.code == "chain_broken"
        with pytest.raises(AuditError) as exc:
            _append(store, "d-002", entry_type="abstain", payload={"v": 2})
        assert exc.value.code == "chain_broken"


@pytest.mark.unit
def test_n21c_invalid_field_corruption_detected(tmp_path):
    """INV-005: a corrupted non-payload field (bad timestamp) fails verification."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute("UPDATE audit_records SET timestamp = 'no-tz' WHERE record_id='d-001'")
        result = store.verify_chain()
        assert not result.ok
        assert result.reason in ("invalid_timestamp", "chain_broken")
        with pytest.raises(AuditError) as exc:
            store.final_decision("r-1")
        assert exc.value.code == "chain_broken"


@pytest.mark.unit
def test_n22_missing_middle_row_detected(tmp_path):
    """INV-005: a controlled mid-chain deletion is detected by verify_chain (threat fixture)."""
    with _open(tmp_path) as store:
        _append(store, "a", payload={"v": 1})
        _append(store, "b", entry_type="abstain", payload={"v": 2})
        _append(store, "c", entry_type="abstain", payload={"v": 3})
        store._conn.execute("DROP TRIGGER audit_no_delete")
        store._conn.execute("DELETE FROM audit_records WHERE record_id = 'b'")
        result = store.verify_chain()
        assert not result.ok
        assert result.reason in ("chain_broken", "missing_record")


@pytest.mark.unit
def test_n23_orphan_row_detected(tmp_path):
    """INV-005: an orphan row injected into the middle is detected, not just the head."""
    with _open(tmp_path) as store:
        _append(store, "a", payload={"v": 1})
        _append(store, "b", entry_type="abstain", payload={"v": 2})
        # Insert an orphan directly, bypassing append, with a broken predecessor link.
        store._conn.execute(
            "INSERT INTO audit_records "
            "(record_id, run_id, timestamp, entry_type, payload_ref, rules_version, "
            "previous_record_id, previous_hash, record_hash, supersedes, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("orphan", "r-1", TS, "abstain", payload_ref({"x": 1}), RULES,
             "nonexistent", "deadbeef", "deadbeef", None, canonical_json({"x": 1}).decode()),
        )
        result = store.verify_chain()
        assert not result.ok
        assert result.reason in ("chain_broken", "orphan_record")


@pytest.mark.unit
def test_n24_append_refused_on_broken_chain(tmp_path):
    """INV-005: append refuses to write when the existing chain is broken."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute(
            "UPDATE audit_records SET payload = ? WHERE record_id = 'd-001'",
            (json.dumps({"v": 999}, sort_keys=True, separators=(",", ":")),),
        )
        with pytest.raises(AuditError) as exc:
            _append(store, "d-002", entry_type="abstain", payload={"v": 2})
        assert exc.value.code == "chain_broken"
        assert store.get("d-002") is None


@pytest.mark.unit
def test_n25_authoritative_reads_refuse_broken_chain(tmp_path):
    """INV-005: final_decision/project refuse to return on a broken chain."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"v": 1})
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute("UPDATE audit_records SET record_hash = 'x' WHERE record_id='d-001'")
        with pytest.raises(AuditError) as exc:
            store.final_decision("r-1")
        assert exc.value.code == "chain_broken"
        with pytest.raises(AuditError) as exc:
            store.project("r-1")
        assert exc.value.code == "chain_broken"


@pytest.mark.unit
def test_n26_trusted_head_detects_truncation(tmp_path):
    """FR-005: a controlled tail truncation is caught by trusted_head (head_mismatch)."""
    with _open(tmp_path) as store:
        _append(store, "a", payload={"v": 1})
        _append(store, "b", entry_type="abstain", payload={"v": 2})
        trusted = store.head()
        store._conn.execute("DROP TRIGGER audit_no_delete")
        store._conn.execute("DELETE FROM audit_records WHERE record_id = 'b'")
        result = verify_against_trusted_head(store, trusted)
        assert not result.ok
        assert result.reason == "head_mismatch"


@pytest.mark.unit
def test_n26b_trusted_head_malformed_input_review(tmp_path):
    """FR-005: malformed trusted head input returns review, not AttributeError."""
    with _open(tmp_path) as store:
        _append(store, "a", payload={"v": 1})
        bad_inputs = [None, {}, "notadict", {"record_id": "a"},
                      {"record_id": "a", "record_hash": "h", "count": True}]
        for bad in bad_inputs:
            result = verify_against_trusted_head(store, bad)
            assert not result.ok
            assert result.reason == "head_mismatch"


@pytest.mark.unit
def test_n26c_trusted_head_rejects_corrupted_middle(tmp_path):
    """FR-005: an equal head over a corrupted middle still fails (chain checked first)."""
    with _open(tmp_path) as store:
        _append(store, "a", payload={"v": 1})
        _append(store, "b", entry_type="abstain", payload={"v": 2})
        trusted = store.head()
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute(
            "UPDATE audit_records SET payload = ? WHERE record_id = 'a'",
            (json.dumps({"v": 999}, sort_keys=True, separators=(",", ":")),),
        )
        result = verify_against_trusted_head(store, trusted)
        assert not result.ok
        assert result.reason == "chain_broken"


@pytest.mark.unit
def test_n26d_registry_non_dict_review(tmp_path):
    """NFR-003: a non-dict replay registry yields review instead of raising."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, _market_gate(dict(inputs)))
        for bad_registry in (None, "notadict", 123):
            result = replay_record(store.get("g-1"), bad_registry)
            assert result.status == "review"
            assert result.reason == "gate_missing"


@pytest.mark.unit
def test_n27_replay_mismatch_review(tmp_path):
    """NFR-003: a recorded observed that disagrees with the re-executed callback yields review."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, {"decision": "abstain", "reason": "wrong"})
        result = replay_record(store.get("g-1"), _registry())
        assert result.status == "review"
        assert result.reason == "observed_mismatch"


@pytest.mark.unit
def test_n28_replay_run_chain_precheck(tmp_path):
    """FR-005: replay_run on a broken chain returns an overall review without replaying."""
    with _open(tmp_path) as store:
        inputs = {"available": 1, "required": 1}
        _append_gate(store, "g-1", "market", inputs, _market_gate(dict(inputs)))
        store._conn.execute("DROP TRIGGER audit_no_update")
        store._conn.execute("UPDATE audit_records SET record_hash = 'x' WHERE record_id='g-1'")
        result = replay_run(store, "r-1", _registry())
        assert result.status == "review"
        assert result.results == []


@pytest.mark.unit
def test_n29_no_cross_leaf_imports_by_ast(tmp_path):
    """NFR-005: AST scan of every audit .py shows no cross-leaf imports."""
    forbidden = {"evidence", "budget", "safety", "data_quality"}
    offenders: list[str] = []
    for path in AUDIT_PKG_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if "course" in parts:
                        idx = parts.index("course")
                        if idx + 1 < len(parts) and parts[idx + 1] in forbidden:
                            offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                parts = module.split(".")
                if "course" in parts:
                    idx = parts.index("course")
                    if idx + 1 < len(parts) and parts[idx + 1] in forbidden:
                        offenders.append(f"{path.name}: from {module}")
    assert offenders == []


@pytest.mark.unit
def test_n30_standalone_demo_without_third_party(tmp_path):
    """NFR-005: `python -S -m audit --demo` works with no site-packages or other leaves."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, "-S", "-m", "audit", "--demo"],
        cwd=str(COURSE_DIR),
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Traceback" not in proc.stderr


@pytest.mark.unit
def test_n31_zero_gate_run_inconclusive_not_pass(tmp_path):
    """NFR-003: a run with no gate records is inconclusive, never a 100% pass."""
    with _open(tmp_path) as store:
        _append(store, "d-001", payload={"note": "narrative only"})
        _append(store, "abs-1", entry_type="abstain", payload={"note": "no gates"})
        result = replay_run(store, "r-1", _registry())
        assert result.status == "inconclusive"
        assert result.gate_total == 0
        assert result.to_dict()["status"] != "pass"


@pytest.mark.unit
def test_n32_invalid_revision_order_with_consistent_hash(tmp_path):
    """INV-005: a self-consistent-hash revision targeting an old (non-terminal) head
    is rejected by semantics, proving verification is not only a hash check.

    The unique supersede index is dropped *in the test* solely to inject the
    threat fixture; the production index is unchanged.
    """
    from tradingagents.course.audit.records import compute_record_hash

    with _open(tmp_path) as store:
        _append(store, "d-001")
        _append(store, "rev-a", entry_type="revision", payload={"x": 1}, supersedes="d-001")
        _append(store, "rev-b", entry_type="revision", payload={"x": 2}, supersedes="rev-a")
        last = store.get("rev-b")
        rogue_payload = {"x": 3}
        fields = {
            "record_id": "rogue-rev",
            "run_id": "r-1",
            "timestamp": TS,
            "entry_type": "revision",
            "payload_ref": payload_ref(rogue_payload),
            "rules_version": RULES,
            "previous_record_id": last.record_id,
            "previous_hash": last.record_hash,
            "supersedes": "rev-a",  # already-superseded, not the current terminal
            "payload": rogue_payload,
        }
        # Drop ONLY the unique index so the threat fixture can be inserted; this
        # is a test-only concession and does not alter runtime constraints.
        store._conn.execute("DROP INDEX ux_audit_single_supersede")
        store._conn.execute(
            "INSERT INTO audit_records "
            "(record_id, run_id, timestamp, entry_type, payload_ref, rules_version, "
            "previous_record_id, previous_hash, record_hash, supersedes, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("rogue-rev", "r-1", TS, "revision", fields["payload_ref"], RULES,
             last.record_id, last.record_hash, compute_record_hash(fields), "rev-a",
             canonical_json(rogue_payload).decode()),
        )
        result = store.verify_chain()
        assert not result.ok
        assert result.reason == "invariant_violation"
        with pytest.raises(AuditError) as exc:
            store.final_decision("r-1")
        assert exc.value.code == "invariant_violation"
