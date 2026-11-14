"""Standalone demo for the audit leaf module.

Run from ``tradingagents/course`` (standard library only, no site-packages,
no top-level ``tradingagents`` import, no dotenv)::

    python -S -m audit --demo

The demo uses a fresh temporary database each run and prints readable JSON. It
returns exit code 0 only when every expected success and expected failure
scenario (pass, review, head mismatch, etc.) behaves as intended. Anchors:
FR-005, INV-005, NFR-003, NFR-004; ADR-003 §2.9.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .replay import replay_record, replay_run, verify_against_trusted_head
from .store import AuditStore

_TS = "2026-11-14T17:00:00+08:00"
_RULES = "v1"


def _gate_market_status(inputs: dict) -> dict:
    """Deterministic demo gate: a D-shaped data-quality result."""
    sufficient = inputs.get("available_domains", 0) >= inputs.get("required_domains", 1)
    return {
        "decision": "proceed" if sufficient else "abstain",
        "insufficient_domains": [] if sufficient else ["market"],
        "labels": inputs.get("labels", {}),
        "reason": "sufficient" if sufficient else "insufficient",
        "violations": [],
        "analysis_cutoff": inputs.get("analysis_cutoff"),
    }


def _gate_safety(inputs: dict) -> dict:
    """Deterministic demo gate: a C-shaped safety result."""
    accepted = bool(inputs.get("units", 0) > 0 or inputs.get("is_noop", False))
    return {
        "accepted": accepted,
        "reason_code": None if accepted else "invalid_units",
        "status": "accepted" if accepted else "rejected",
        "action": inputs.get("action"),
        "rule_version": inputs.get("rule_version", _RULES),
        "snapshot_id": inputs.get("snapshot_id"),
        "instrument": inputs.get("instrument"),
        "is_noop": inputs.get("is_noop", False),
        "ignored_claims": [],
    }


def _registry() -> dict:
    return {
        "market_status": {_RULES: _gate_market_status},
        "safety": {_RULES: _gate_safety},
    }


def run_demo() -> int:
    """Execute the demo and return process exit code (0 == all expectations met)."""
    checks: list[dict] = []

    def expect(name: str, ok: bool, detail: object) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    with tempfile.TemporaryDirectory(prefix="audit-demo-") as tmp:
        db_path = str(Path(tmp) / "demo.sqlite")

        with AuditStore.open(db_path) as store:
            # 1. initial decision
            d1 = store.append(
                record_id="dec-1",
                run_id="run-demo",
                timestamp=_TS,
                entry_type="decision",
                payload={"action": "hold", "units": 0, "note": "initial"},
                rules_version=_RULES,
            )
            expect("append initial decision", d1.record_id == "dec-1", d1.to_dict())

            # 2. a review-flagged rejection is recorded and searchable
            rej = store.append(
                record_id="rej-1",
                run_id="run-demo",
                timestamp=_TS,
                entry_type="rejection",
                payload={"outcome": "review", "reason": "ambiguous_evidence"},
                rules_version=_RULES,
            )
            expect("rejection(review) recorded", rej.payload["outcome"] == "review", rej.to_dict())

            # 3. two revisions; the old rows stay queryable
            store.append(
                record_id="rev-1",
                run_id="run-demo",
                timestamp=_TS,
                entry_type="revision",
                payload={"action": "buy", "units": 10},
                rules_version=_RULES,
                supersedes="dec-1",
            )
            store.append(
                record_id="rev-2",
                run_id="run-demo",
                timestamp=_TS,
                entry_type="revision",
                payload={"action": "buy", "units": 5},
                rules_version=_RULES,
                supersedes="rev-1",
            )
            expect(
                "old decision still queryable",
                store.get("dec-1") is not None and store.get("rev-1") is not None,
                {"dec-1": store.get("dec-1") is not None, "rev-1": store.get("rev-1") is not None},
            )

            # 4. one unique terminal decision
            final = store.final_decision("run-demo")
            expect("unique final decision is rev-2", final.record_id == "rev-2", final.to_dict())

            # 5. replay success: append gate records whose observed matches the callback
            market_inputs = {
                "available_domains": 2,
                "required_domains": 1,
                "labels": {"market": "available"},
                "analysis_cutoff": "2026-11-13",
            }
            safety_inputs = {
                "action": "buy",
                "units": 5,
                "is_noop": False,
                "rule_version": _RULES,
                "snapshot_id": "snap-1",
                "instrument": "AAA",
            }
            store.append(
                record_id="gate-mkt-1",
                run_id="run-demo",
                timestamp=_TS,
                entry_type="rejection",
                payload={
                    "gate_id": "market_status",
                    "rules_version": _RULES,
                    "inputs": market_inputs,
                    "observed": _gate_market_status(dict(market_inputs)),
                    "outcome": "gate",
                },
                rules_version=_RULES,
            )
            store.append(
                record_id="gate-safe-1",
                run_id="run-demo",
                timestamp=_TS,
                entry_type="rejection",
                payload={
                    "gate_id": "safety",
                    "rules_version": _RULES,
                    "inputs": safety_inputs,
                    "observed": _gate_safety(dict(safety_inputs)),
                    "outcome": "gate",
                },
                rules_version=_RULES,
            )

            registry = _registry()
            rec = store.get("gate-mkt-1")
            single = replay_record(rec, registry)
            expect("replay_record pass", single.status == "pass", single.to_dict())

            run_result = replay_run(store, "run-demo", registry)
            expect(
                "replay_run pass over gate records",
                run_result.status == "pass" and run_result.gate_total >= 2,
                run_result.to_dict(),
            )

            # 6. replay mismatch -> review: record an observed that disagrees
            bad_inputs = {"available_domains": 0, "required_domains": 1}
            store.append(
                record_id="gate-bad-1",
                run_id="run-demo",
                timestamp=_TS,
                entry_type="rejection",
                payload={
                    "gate_id": "market_status",
                    "rules_version": _RULES,
                    "inputs": bad_inputs,
                    "observed": {"decision": "proceed", "note": "deliberately wrong"},
                    "outcome": "gate",
                },
                rules_version=_RULES,
            )
            bad = replay_record(store.get("gate-bad-1"), registry)
            expect("replay mismatch -> review", bad.status == "review", bad.to_dict())

            # 7. trusted head: exact match passes; after a legitimate append it
            #    changes, so the old checkpoint reports head_mismatch (review).
            trusted = store.head()
            match = verify_against_trusted_head(store, trusted)
            expect("trusted head match", match.ok, match.to_dict())

            store.append(
                record_id="post-head",
                run_id="run-demo",
                timestamp=_TS,
                entry_type="abstain",
                payload={"reason": "post-head stress"},
                rules_version=_RULES,
            )
            mismatch = verify_against_trusted_head(store, trusted)
            expect(
                "trusted head mismatch -> review",
                (not mismatch.ok) and mismatch.reason == "head_mismatch",
                mismatch.to_dict(),
            )

            chain = store.verify_chain()
            expect("chain verifies", chain.ok, chain.to_dict())

    all_ok = all(item["ok"] for item in checks)
    print(
        json.dumps(
            {"demo": "audit", "all_expected": all_ok, "checks": checks},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if all_ok else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; supports ``--demo`` (FR-005, ADR-003 §2.9)."""
    parser = argparse.ArgumentParser(prog="audit", description="Standalone audit module demo")
    parser.add_argument("--demo", action="store_true", help="run the standalone audit demo")
    args = parser.parse_args(argv)
    if not args.demo:
        parser.print_help()
        return 2
    return run_demo()


if __name__ == "__main__":  # pragma: no cover - script entry
    sys.exit(main())
