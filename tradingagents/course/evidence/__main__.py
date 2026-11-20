"""Deterministic offline demo for the evidence leaf (FR-001 / INV-001 / ADR-005).

Run with ``python -m tradingagents.course.evidence --demo``. The demo uses only
the standard library, no clock/RNG and no network: it builds one run-scoped
registry and prints deterministic JSON for the fixed EVAL-008, EVAL-009 and
EVAL-006 examples.
"""

from __future__ import annotations

import argparse
import json

from .claims import verify_claim
from .contracts import EvidenceRegistry, Fact, FreshnessPolicy

_RUN_ID = "demo-run"
_AS_OF = "2026-09-01"
_POLICY = FreshnessPolicy(name="demo", max_age_days=2)


def _macd_fact() -> Fact:
    """Build the canonical MACD golden-cross fact used by the demo."""
    return Fact.from_record(
        {
            "subject": "NVDA",
            "metric": "macd_cross",
            "value": None,
            "relation": "golden_cross",
            "unit": None,
            "period": "2026-08-30",
        }
    )


def _evidence(evidence_id: str, published_at: str, available_as_of: str, fact: Fact) -> dict:
    """Build one collector-supplied evidence record for the demo run."""
    return {
        "evidence_id": evidence_id,
        "run_id": _RUN_ID,
        "source": "tool",
        "content_ref": f"snapshot:NVDA:{published_at}",
        "status": "available",
        "published_at": published_at,
        "available_as_of": available_as_of,
        "fact": fact.to_dict(),
        "freshness_policy": _POLICY.name,
    }


def _demo_payloads() -> list[tuple[str, dict]]:
    """Return the labelled, deterministic demo verdict payloads."""
    fact = _macd_fact()
    registry = EvidenceRegistry.build(
        run_id=_RUN_ID,
        as_of=_AS_OF,
        candidates=[
            _evidence("ev-1", "2026-08-30", "2026-08-30", fact),
            _evidence("ev-future", "2026-08-30", "2026-09-05", fact),
        ],
    )
    accepted = verify_claim(
        {
            "claim_id": "EVAL-008",
            "text": "MACD golden cross",
            "classification": "factual",
            "fact": fact.to_dict(),
            "evidence_refs": ["ev-1"],
        },
        registry=registry,
        policy=_POLICY,
    )
    future = registry.admissibility("ev-future", _POLICY)
    prediction = verify_claim(
        {
            "claim_id": "EVAL-006",
            "text": "MACD 金叉，股价必涨",
            "fact": fact.to_dict(),
            "evidence_refs": ["ev-1"],
        },
        registry=registry,
        policy=_POLICY,
    )
    return [
        ("EVAL-008", accepted.to_dict()),
        ("EVAL-009", future.to_dict()),
        ("EVAL-006", prediction.to_dict()),
    ]


def main(argv: list[str] | None = None) -> int:
    """Run the deterministic offline evidence demo (FR-001 / INV-001 / ADR-005).

    Returns 0 after printing three deterministic JSON lines; without ``--demo`` it
    prints help and returns 2.
    """
    parser = argparse.ArgumentParser(prog="python -m tradingagents.course.evidence")
    parser.add_argument("--demo", action="store_true", help="run the deterministic offline demo")
    args = parser.parse_args(argv)
    if not args.demo:
        parser.print_help()
        return 2
    for label, payload in _demo_payloads():
        print(f"{label} {json.dumps(payload, sort_keys=True, allow_nan=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
