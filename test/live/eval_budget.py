"""Live evaluation driver for the FR-002 budget (run where the deps and a key exist).

It runs the same ticker and date twice: once on the untouched baseline and once
with the budget ledger attached, then prints and saves a comparison.

This is the only place that spends money, so it is explicit about what it does:

    python test/live/eval_budget.py --ticker NVDA --date 2026-09-01 --rounds 1

Requirements on the machine that runs it:
    pip install -e .
    pip install -r requirements-course.txt
    a .env with the provider key (never commit it)

The output JSON is safe to share: it contains token counts, timings and the
decision, but no key and no prompt text.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def build_config(rounds: int, out_dir: Path) -> dict:
    """Copy the default config and point every writable path inside the repo."""
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = rounds
    config["max_risk_discuss_rounds"] = rounds
    config["results_dir"] = str(out_dir / "logs")
    config["data_cache_dir"] = str(out_dir / "cache")
    config["memory_log_path"] = str(out_dir / "memory" / "trading_memory.md")
    return config


def run_once(
    ticker: str,
    date: str,
    *,
    with_budget: bool,
    limit_tokens: int,
    rounds: int,
    out_dir: Path,
) -> dict:
    from tradingagents.course.budget.contracts import LedgerConfig
    from tradingagents.course.budget.ledger import BudgetLedger
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    ledger = None
    if with_budget:
        ledger = BudgetLedger(LedgerConfig(limit_tokens=limit_tokens))

    graph = TradingAgentsGraph(debug=False, config=build_config(rounds, out_dir), budget=ledger)

    started = time.perf_counter()
    state, decision = graph.propagate(ticker, date)
    elapsed = time.perf_counter() - started

    record = {
        "mode": "budget" if with_budget else "baseline",
        "ticker": ticker,
        "date": date,
        "rounds": rounds,
        "wall_seconds": round(elapsed, 2),
        "decision": decision if isinstance(decision, (str, dict, list, int, float)) else str(decision),
    }

    if ledger is not None:
        snapshot = ledger.snapshot()
        events = ledger.events()
        record.update(
            {
                "limit_tokens": snapshot["limit_tokens"],
                "spent_tokens": snapshot["spent"],
                "remaining_tokens": snapshot["remaining_global"],
                "reservations": snapshot["reservations"],
                "level": snapshot["level"],
                "state": snapshot["state"],
                "event_count": len(events),
                "degradations": sum(1 for event in events if event.type == "degraded"),
            }
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a baseline run with a budgeted run.")
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--date", default="2026-09-01")
    parser.add_argument("--rounds", type=int, default=1, help="debate rounds (1 keeps the cost low)")
    parser.add_argument("--limit-tokens", type=int, default=240_000)
    parser.add_argument("--skip-baseline", action="store_true", help="only run the budgeted pass")
    parser.add_argument("--out", default=str(REPO_ROOT / "eval_results"))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    if not args.skip_baseline:
        print("[1/2] baseline run (no ledger) ...", flush=True)
        results.append(
            run_once(
                args.ticker, args.date,
                with_budget=False,
                limit_tokens=args.limit_tokens,
                rounds=args.rounds,
                out_dir=out_dir,
            )
        )
    print("[2/2] budgeted run (ledger attached) ...", flush=True)
    results.append(
        run_once(
            args.ticker, args.date,
            with_budget=True,
            limit_tokens=args.limit_tokens,
            rounds=args.rounds,
            out_dir=out_dir,
        )
    )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ticker": args.ticker,
        "date": args.date,
        "rounds": args.rounds,
        "runs": results,
    }
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"budget_eval_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n== summary ==")
    for run in results:
        line = f"{run['mode']:<9} {run['wall_seconds']:>7.1f}s  decision={run['decision']}"
        if "spent_tokens" in run:
            line += f"  tokens={run['spent_tokens']}  level=L{run['level']}  events={run['event_count']}"
        print(line)
    print(f"\nwritten: {path}")
    print("Share this JSON file: it holds no key and no prompt text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
