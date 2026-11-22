"""Collect the facts the demo page shows, straight from the repository.

The page must not display hand-written numbers, so every figure it renders is
produced here and written to `demo/data.json`. Re-run this whenever the code
changes:

    python -m demo.collect

What is collected:

* the baseline run recorded in `docs/baseline.md`
* the budget replay table produced by `tradingagents.course.budget.replay`
* the requirement-to-component pairs parsed from `docs/architecture/trace-matrix.md`
* the review rounds from `docs/review-memo.md` and defects from `docs/bug-diary.md`
* the offline test files that exist for each module

Nothing here needs a model, a key or network access.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "data.json"

MODULES = {
    "A": {"name": "Evidence-grounded debate", "pkg": "evidence",
          "reqs": ["FR-001", "INV-001"]},
    "B": {"name": "Run budget", "pkg": "budget",
          "reqs": ["FR-002", "FR-006", "INV-002", "INV-006"]},
    "C": {"name": "Deterministic simulation safety", "pkg": "safety",
          "reqs": ["FR-003", "INV-003", "SEC-001"]},
    "D": {"name": "Data sufficiency", "pkg": "data_quality",
          "reqs": ["FR-004", "INV-004"]},
    "E": {"name": "Verifiable audit", "pkg": "audit",
          "reqs": ["FR-005", "INV-005"]},
}


def baseline() -> dict:
    """Read the one recorded baseline run out of docs/baseline.md."""
    text = (ROOT / "docs" / "baseline.md").read_text(encoding="utf-8")
    figures: dict[str, object] = {}
    for label, key in (
        ("LLM 调用次数", "calls"),
        ("总 tokens", "tokens"),
        ("耗时", "seconds"),
        ("最终信号", "signal"),
    ):
        match = re.search(rf"\|\s*{label}\s*\|\s*([^|]+)\|", text)
        if match:
            figures[key] = match.group(1).strip()

    if "calls" in figures:
        figures["calls"] = int(re.sub(r"[^\d]", "", str(figures["calls"])))
    if "tokens" in figures:
        figures["tokens"] = int(re.sub(r"[^\d]", "", str(figures["tokens"])))
    if "seconds" in figures:
        figures["seconds"] = float(re.sub(r"[^\d.]", "", str(figures["seconds"])))
    return figures


def budget_replay() -> list[dict]:
    """Run the deterministic replay; the numbers are computed, never copied."""
    sys.path.insert(0, str(ROOT))
    from tradingagents.course.budget.replay import BASELINE_TOTAL_TOKENS, compare

    rows = []
    for result in compare([240_000, 200_000, 180_000, 150_000, 120_000]):
        rows.append(
            {
                "label": "No cap (baseline)" if result.limit_tokens is None
                else f"{result.limit_tokens:,}",
                "limit": result.limit_tokens,
                "calls": result.calls_executed,
                "tokens": result.total_tokens,
                "delta": round((result.total_tokens / BASELINE_TOTAL_TOKENS - 1) * 100, 1),
                "level": result.level,
                "degradations": result.degradations,
                "skipped": result.skipped,
            }
        )
    return rows


def trace_pairs() -> list[dict]:
    """Requirement -> enforcing component pairs from the trace matrix."""
    text = (ROOT / "docs" / "architecture" / "trace-matrix.md").read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        match = re.match(r"\|\s*(?:\*\*)?([A-Z]+-\d{3})(?:\*\*)?\s*\|\s*([^|]+)\|", line)
        if match:
            rows.append({"id": match.group(1), "component": match.group(2).strip()})
    return rows


def review_rounds() -> list[str]:
    """One line per review entry, taken from the headings of the memo."""
    text = (ROOT / "docs" / "review-memo.md").read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        if line.startswith("#### Round") or line.startswith("### PR"):
            out.append(line.lstrip("# ").strip())
    return out


def defects() -> list[dict]:
    text = (ROOT / "docs" / "bug-diary.md").read_text(encoding="utf-8")
    out = []
    for block in re.split(r"\n(?=- id: BUG-)", text):
        bug = re.search(r"- id: (BUG-\d+)", block)
        title = re.search(r"title: (.+)", block)
        status = re.search(r"status: (\w+)", block)
        if bug:
            out.append(
                {
                    "id": bug.group(1),
                    "title": title.group(1).strip() if title else "",
                    "status": status.group(1) if status else "",
                }
            )
    return out


def tests_per_module() -> dict[str, list[str]]:
    files = sorted(p.name for p in (ROOT / "test" / "offline").glob("test_*.py"))
    mapping: dict[str, list[str]] = {role: [] for role in MODULES}
    mapping["Integration"] = []
    for name in files:
        stem = name.removeprefix("test_").removesuffix(".py")
        for role, meta in MODULES.items():
            if meta["pkg"] in stem:
                mapping[role].append(name)
        if "pipeline" in stem:
            mapping["Integration"].append(name)
    return mapping


def main() -> int:
    payload = {
        "baseline": baseline(),
        "replay": budget_replay(),
        "trace": trace_pairs(),
        "reviews": review_rounds(),
        "defects": defects(),
        "tests": tests_per_module(),
        "modules": MODULES,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  baseline : {payload['baseline']}")
    print(f"  replay   : {len(payload['replay'])} rows")
    print(f"  trace    : {len(payload['trace'])} requirement rows")
    print(f"  reviews  : {len(payload['reviews'])} entries")
    print(f"  defects  : {len(payload['defects'])} entries")
    print(f"  tests    : {sum(len(v) for v in payload['tests'].values())} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
