# Demo page

A single page that shows what the five course modules actually do, built from the repository
itself. No model, no API key, no network.

## Run it

Double-click `start-demo.cmd` in the repository root, or from a terminal:

```bash
python -m demo.serve
```

The launcher regenerates `demo/data.json`, starts a server on `127.0.0.1` (first free port at or
above 8765), and opens the page in your browser. Close the window to stop it.

## What it shows

| Section | Content | Where it comes from |
|---|---|---|
| Baseline run | 19 calls, 228,275 tokens, 150.61 s, decision `Hold` | `docs/baseline.md` |
| Run budget | What five caps do to the same run, with the degradation level reached | `tradingagents.course.budget.replay` — computed on every launch |
| Modules | Each role, its requirements, and its test files | `tradingagents/course/*` and `test/offline/` |
| Traceability | Requirement to enforcing component | `docs/architecture/trace-matrix.md` |
| Process evidence | Review rounds and recorded defects | `docs/review-memo.md`, `docs/bug-diary.md` |

## The rule this page follows

**Every number is produced by code, never typed by hand.** `demo/collect.py` reads the documents
and calls `replay.compare()`; `demo/serve.py` runs the collector before serving. If a figure in the
page is wrong, it is wrong in the code that produced it.

That is the same rule the report follows, and it is why the budget row for 240,000 shows `L0` with
zero skipped calls: that figure comes from the regression test for BUG-004, not from a sentence
someone wrote.

## What it does not do

- It does not run a live analysis and it does not call a model. The budget table is a **deterministic
  replay** of the recorded baseline; the page says so above the table.
- It does not expose a web API, a database, or credentials. It is a static folder plus a file
  server bound to loopback.
- It does not replace `report_html.py`, which renders a full analysis report and needs a real run.

## Regenerate the data without the page

```bash
python -m demo.collect
```

Useful after changing `replay.py`, the trace matrix, or the review memo.

## Tests

```bash
python -m pytest -o testpaths=test/offline test/offline/test_demo_collect.py -q
```

Eight tests check the shape and the provenance of the collected facts, including that the 240,000
cap stays at `L0` (the BUG-004 regression) and that the replay rows match what the module computes.

> Note: the repository's CI runs `pytest` over `tests/` only, and `course-bootstrap` runs
> `test/offline/test_course_scaffold.py`. These demo tests are therefore run locally, not in CI.
