# ADR-006: Evidence → Debate Integration (FR-001 M3)

- **Status:** PROPOSED (not APPROVED). This ADR claims no course compliance (see `DEVELOPMENT-POLICY.md`; G-1/D9 are not met).
- **Scope:** Role A, FR-001 M3. Integration only; no new pre-coding approval is implied.

## Context

FR-001 needs the evidence ledger to ground the bull/bear debate without changing the
default `TradingAgentsGraph` behavior. Existing graph methods, the research manager, and
the debate state schema must stay untouched so the default entry point remains identical.

## Decision

### Accepted input

`evidence_context` is an accepted JSON object with exactly these members:

- `as_of` — canonical `YYYY-MM-DD` date the evidence view is pinned to.
- `registry` — a serialized `EvidenceRegistry` (A M2 contract).
- `policy` — a serialized `FreshnessPolicy` (A M2 contract).
- `data_admission_decision` — **optional**. Absent is allowed; when present, only the exact
  string `"proceed"` allows the run. Any other present value (including wrong types) is a
  non-proceed and blocks the run.

The runtime **never trusts model-supplied evidence**. Only registry entries may be cited;
the model is not a source of evidence.

### Changed files (only these)

- `docs/architecture/adr/006-evidence-debate-integration.md` (this record)
- `tradingagents/course/evidence/integration.py` (new)
- `tradingagents/course/evidence/__init__.py` (exports)
- `tradingagents/course/evidence/README.md` (docs)
- `tradingagents/agents/state.py` (AgentState)
- `tradingagents/agents/researchers/bull_researcher.py`
- `tradingagents/agents/researchers/bear_researcher.py`
- `tradingagents/graph/trading_graph.py` (one new last method)
- `test/offline/test_evidence_integration.py` (new offline test)

No changes to existing graph methods, the research manager, or the debate state schema.

### New graph entry point

A single method is **appended last** to `TradingAgentsGraph`:

```python
def propagate_with_evidence(
    self,
    company_name,
    trade_date,
    *,
    evidence_context,
    asset_type="stock",
    portfolio=None,
):
    ...
```

The existing `propagate(...)` entry point is unchanged; its behavior is identical.

### AgentState

Two `NotRequired` fields are **appended** to `AgentState` (no existing fields change):

- `evidence_context` — the validated accepted context carried through the graph.
- `evidence_verdicts` — the E-layer audit records produced for this run.

### Fail-closed ordering (reject before any model call)

An invalid `evidence_context`, an invalid `as_of`/trade date, or a checkpoint rejection
aborts **before** any model invocation. A present non-proceed returns `REVIEW`/abstain with
**no model call**, including the direct researcher fallback path — researchers must not be
called directly around the gate. An absent optional decision is allowed.

### D statuses

Supplied status labels align with D: exactly `available`, `unavailable`, or `unknown`.
Only `available` units may be admitted; missing or malformed provenance cannot be
admitted. A does not invent an `available` or `neutral` status.

### E audit format

The records are E-compatible, strict, pure JSON; A does not own or persist them. Each
record contains `speaker`, `round`, `verdicts`, `rejected_refs`, `as_of`, and `run_id`.
No free text is embedded in the record.

### Model contract

The model returns only `{"claims": [...]}`. Raw model text is **never** used for the
accepted projection or for abstention. The integration safely handles identifier injection,
unknown-field injection, and duplicate-key injection by rejecting non-conforming output.
A factual claim with insufficient admitted references abstains; a prediction remains a
hypothesis. No uncited factual claim is promoted to accepted evidence.

## Consequences

- Grounded debate is opt-in via `propagate_with_evidence`; default behavior is unchanged.
- Rollback is limited to the integration: remove `integration.py`, its exports/docs, the
  two `AgentState` fields, the researcher hooks, and the `propagate_with_evidence` method.

## Verification

- Coverage A10–A13 is local boundary graph coverage with the **real compiled graph** and
  **scripted models** (offline).
- A14 full B/C/D/E interoperability **remains PENDING** until PRs #3/#4/#5/M3 share a baseline.
