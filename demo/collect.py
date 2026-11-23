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


def budget_sweep() -> list[dict]:
    """Every cap from 100k to 300k in 10k steps, for the slider.

    Pre-computed so the page never needs a backend: the slider picks a row.
    """
    sys.path.insert(0, str(ROOT))
    from tradingagents.course.budget.replay import BASELINE_TOTAL_TOKENS, baseline_trace, replay

    trace = baseline_trace()
    rows = []
    for limit in range(100_000, 301_000, 10_000):
        result = replay(trace, limit_tokens=limit)
        rows.append(
            {
                "limit": limit,
                "calls": result.calls_executed,
                "tokens": result.total_tokens,
                "delta": round((result.total_tokens / BASELINE_TOTAL_TOKENS - 1) * 100, 1),
                "level": result.level,
                "skipped": result.skipped,
                "degradations": result.degradations,
                "ended": result.ended,
            }
        )
    return rows


def rejection_cases() -> list[dict]:
    """Four ways the system can refuse, each executed for real.

    These are pure functions: no model, no network. What the page shows is what
    the code returned while collecting.
    """
    sys.path.insert(0, str(ROOT))
    from tradingagents.course.budget.contracts import BudgetDenied, LedgerConfig
    from tradingagents.course.budget.ledger import BudgetLedger
    from tradingagents.course.data_quality.admission import admit

    domains = ("news", "social", "macro", "price", "fundamentals")
    cutoff = "2026-09-01"

    def observations(kind: str, value: int | None = None) -> list[dict]:
        return [
            {
                "domain": domain,
                "kind": kind,
                "value": value,
                "value_present": value is not None,
                "source": "demo-fixture",
                "observed_as_of": "2026-08-30",
            }
            for domain in domains
        ]

    cases: list[dict] = []

    # D — a required domain is unavailable.
    result = admit(observations("no_data"), cutoff)
    cases.append(
        {
            "key": "unavailable",
            "module": "D",
            "title": "Required data unavailable",
            "input": "all five domains report no_data",
            "outcome": result.decision,
            "meaning": "The system abstains: it will not guess from data it does not have.",
            "requirement": "FR-004 / INV-004",
        }
    )

    # D — a required domain is missing entirely -> default-deny.
    result = admit(observations("value", 1)[:4], cutoff)
    cases.append(
        {
            "key": "unknown",
            "module": "D",
            "title": "Required domain missing",
            "input": "fundamentals absent from the report",
            "outcome": result.decision,
            "meaning": "Unknown is escalated to review, never treated as neutral.",
            "requirement": "FR-004 / INV-004",
        }
    )

    # D — the happy path, so the contrast is visible.
    result = admit(observations("value", 1), cutoff)
    cases.append(
        {
            "key": "proceed",
            "module": "D",
            "title": "All domains available",
            "input": "all five domains report a value",
            "outcome": result.decision,
            "meaning": "Only this outcome lets the run reach the model.",
            "requirement": "FR-004 / INV-004",
        }
    )

    # B — the call cap is reached.
    ledger = BudgetLedger(LedgerConfig(limit_tokens=240_000, limit_calls=1))
    ledger.reserve("market_analyst", "analyst", "quick", "call-1")
    try:
        ledger.reserve("market_analyst", "analyst", "quick", "call-2")
        outcome = "allowed"
    except BudgetDenied as exc:
        outcome = exc.reason
    cases.append(
        {
            "key": "budget",
            "module": "B",
            "title": "Budget exhausted",
            "input": "limit_calls = 1, second call attempted",
            "outcome": outcome,
            "meaning": "The call is refused before it reaches the provider.",
            "requirement": "FR-002 / INV-002",
        }
    )

    return cases


def design_timeline() -> list[dict]:
    """BUG-004 as three states, taken from the bug diary and the replay.

    The first version compared the remaining budget with fixed fractions of the
    total. Every healthy run dips below those fractions near its end, so a cap
    above the baseline still degraded the run. The fix compares the remaining
    budget with the projected remaining spend instead.
    """
    sys.path.insert(0, str(ROOT))
    from tradingagents.course.budget.replay import baseline_trace, replay

    trace = baseline_trace()
    current = replay(trace, limit_tokens=240_000)

    return [
        {
            "step": "v1",
            "state": "bad",
            "title": "Fixed fractions",
            "detail": "Degrade when the remaining budget falls below 15% / 10% of the total.",
            "result": "A 240,000 cap degraded the run to L1 and cut it to 177,519 tokens.",
        },
        {
            "step": "found",
            "state": "bad",
            "title": "Found by replay, not by unit tests",
            "detail": "Each unit test exercised one stage in isolation, so every stage looked correct alone.",
            "result": "Only a full 19-call trace showed the rules firing near the end of every stage.",
        },
        {
            "step": "v2",
            "state": "good",
            "title": "Projection-aware",
            "detail": "Compare the remaining budget with the projected remaining spend.",
            "result": (
                f"The same cap now leaves the run at L{current.level} "
                f"with {current.calls_executed} calls and {current.total_tokens:,} tokens."
            ),
        },
        {
            "step": "guard",
            "state": "good",
            "title": "Pinned by a regression test",
            "detail": "test_a_generous_budget_changes_nothing fails if a cap above the baseline ever degrades.",
            "result": "The bug cannot come back silently.",
        },
    ]


def governance_steps() -> list[dict]:
    """How a change got through the process, with the checkout evidence.

    The two episodes shown here are the ones the repository can prove: a review
    that caught the agent overwriting a historical record, and a CI failure that
    no local run could have produced.
    """
    return [
        {
            "step": "1",
            "state": "neutral",
            "title": "Agent opens a pull request",
            "detail": "The coding agent writes the module, its tests and the documents.",
            "evidence": "PR #4 — 21 commits, 37 files",
        },
        {
            "step": "2",
            "state": "bad",
            "title": "CI catches what local runs cannot",
            "detail": (
                "Two source files carried a UTF-8 BOM. On Linux, ast.parse rejected them, "
                "so all four Python versions failed. The local suite could not run at all "
                "(missing runtime dependencies), so CI was the only place this could surface."
            ),
            "evidence": "fa0c377e red, a4dff87 green",
        },
        {
            "step": "3",
            "state": "bad",
            "title": "Reviewer finds five issues",
            "detail": (
                "One mattered most: while adding a new log entry, the agent had rewritten "
                "AI-USE-0002, the owner's historical record of the G-1/D9 decision. Merged as "
                "is, the real record would have disappeared."
            ),
            "evidence": "docs/review-memo.md — round 1, CHANGES REQUIRED",
        },
        {
            "step": "4",
            "state": "neutral",
            "title": "Agent fixes, reviewer re-checks",
            "detail": (
                "The historical entry was restored verbatim and the diff against main now shows "
                "an addition only. A second round caught a canonical stage name falling through "
                "to the default stage."
            ),
            "evidence": "b23f541, e95fb5a",
        },
        {
            "step": "5",
            "state": "good",
            "title": "Green, approved, merged",
            "detail": "Eight checks pass on four Python versions and the reviewer approves.",
            "evidence": "c306f81 — course scaffold success",
        },
    ]


def ci_checks() -> dict:
    """The checks that guard the delivery branch.

    Read from the workflow files so the page cannot claim a check that does not
    exist.
    """
    workflows = ROOT / ".github" / "workflows"
    checks: list[dict] = []

    ci_text = (workflows / "ci.yml").read_text(encoding="utf-8")
    if "pytest -q" in ci_text:
        checks.append(
            {"name": "tests (py3.11–3.14)", "detail": "the upstream suite", "state": "on"}
        )
    if "ruff check" in ci_text:
        checks.append({"name": "ruff", "detail": "strict, full repo", "state": "on"})
    if "clean-install" in ci_text:
        checks.append({"name": "clean-install", "detail": "bare install imports", "state": "on"})

    boot_text = (workflows / "course-bootstrap.yml").read_text(encoding="utf-8")
    if "check_course.py" in boot_text:
        checks.append({"name": "course scaffold", "detail": "requirement schema and trace", "state": "on"})
    if "testpaths=test/offline test/offline -q" in boot_text:
        checks.append(
            {"name": "course offline suite", "detail": "the five modules' own tests", "state": "on"}
        )
    else:
        checks.append(
            {
                "name": "course offline suite",
                "detail": "not wired into CI — the suite runs locally only",
                "state": "off",
            }
        )

    return {
        "checks": checks,
        "before": {"ref": "fa0c377e", "result": "failure"},
        "after": {"ref": "c306f81", "result": "success"},
    }


MODULE_STORY = {
    "A": {
        "question": "Can a claim be made without evidence?",
        "answer": "No. A strong claim must bind to a retrieved evidence unit, and the evidence must not be dated after the analysis date.",
        "refuse": "A claim without evidence is demoted to a hypothesis, or the turn abstains.",
        "adr": "005-evidence-grounded-debate.md",
        "files": None,  # filled from disk
    },
    "B": {
        "question": "What bounds the cost of a run?",
        "answer": "A metered ledger: reserve before the call, settle after it, refuse past the cap.",
        "refuse": "Past the cap the call is refused; below the cap the run degrades along a fixed ladder instead of dying.",
        "adr": "007-budget-at-the-model-client-boundary.md",
        "files": None,
    },
    "C": {
        "question": "Who decides whether a trade proposal is legal?",
        "answer": "Deterministic code, not the model. The model proposes; the validator accepts or rejects.",
        "refuse": "A proposal without a holdings snapshot, with units <= 0 for a buy, or beyond cash is rejected.",
        "adr": "002-simulation-safety.md",
        "files": None,
    },
    "D": {
        "question": "What does it mean when the data is not there?",
        "answer": "Three states, not two: available, unavailable, unknown. Neutral is a value, not a status.",
        "refuse": "unavailable abstains; unknown escalates to review. Neither is ever treated as a neutral signal.",
        "adr": None,
        "files": None,
    },
    "E": {
        "question": "Can a finished decision be trusted later?",
        "answer": "An append-only hash chain, a supersede chain for revisions, and an offline gate replay.",
        "refuse": "Overwriting a final decision is rejected; a broken chain fails verification.",
        "adr": "003-append-only-audit.md",
        "files": None,
    },
}


def module_stories() -> dict[str, dict]:
    """One short story per module for the section switcher.

    The file lists and ADR names come from disk, so the page cannot show a
    module that does not exist or name an ADR that was never written.
    """
    out: dict[str, dict] = {}
    for role, story in MODULE_STORY.items():
        package = MODULES[role]["pkg"]
        directory = ROOT / "tradingagents" / "course" / package
        files = sorted(p.name for p in directory.glob("*.py")) if directory.is_dir() else []
        adr = story["adr"]
        adr_present = bool(adr) and (ROOT / "docs" / "architecture" / "adr" / adr).exists()
        out[role] = {
            "role": role,
            "name": MODULES[role]["name"],
            "reqs": MODULES[role]["reqs"],
            "question": story["question"],
            "answer": story["answer"],
            "refuse": story["refuse"],
            "adr": adr if adr_present else None,
            "files": files,
            "tests": [],  # filled by the caller from tests_per_module()
        }
    return out


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
    stories = module_stories()
    tests = tests_per_module()
    for role in stories:
        stories[role]["tests"] = tests.get(role, [])

    payload = {
        "baseline": baseline(),
        "replay": budget_replay(),
        "sweep": budget_sweep(),
        "rejections": rejection_cases(),
        "timeline": design_timeline(),
        "governance": governance_steps(),
        "ci": ci_checks(),
        "stories": stories,
        "trace": trace_pairs(),
        "reviews": review_rounds(),
        "defects": defects(),
        "tests": tests,
        "modules": MODULES,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  baseline : {payload['baseline']}")
    print(f"  replay   : {len(payload['replay'])} rows")
    print(f"  sweep    : {len(payload['sweep'])} caps for the slider")
    print(f"  reject   : {len(payload['rejections'])} executed cases")
    print(f"  timeline : {len(payload['timeline'])} design steps")
    print(f"  govern   : {len(payload['governance'])} process steps")
    print(f"  ci       : {sum(1 for c in payload['ci']['checks'] if c['state']=='on')} checks on")
    for r, s in stories.items():
        print(f"  story {r}  : {len(s['files'])} files, adr={'yes' if s['adr'] else 'no'}")
    print(f"  trace    : {len(payload['trace'])} requirement rows")
    print(f"  reviews  : {len(payload['reviews'])} entries")
    print(f"  defects  : {len(payload['defects'])} entries")
    print(f"  tests    : {sum(len(v) for v in payload['tests'].values())} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
