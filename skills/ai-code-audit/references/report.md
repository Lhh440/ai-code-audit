# Report format

Keep it short enough that someone reads it. Findings first, no preamble essay.

```markdown
## Claimed
<one sentence from the task/PR: what this diff says it does>

## Actual
<one sentence: what the code does. Divergence here is itself the headline.>

## Evidence run
| step | result |
|---|---|
| check_imports | 2 unresolvable |
| probe_api | 1 hallucinated symbol |
| static_gate | ruff 4, mypy 0 |
| test_credibility | 6 changed tests still pass on revert |
| slop_scan | 11 (3 major) |

Skipped: <tool> (<reason>). A skipped step is not a pass.

## Findings

### F1 — BLOCKER — `app/billing.py:88` — hallucinated symbol
`client.create_charge(amount=...)` — `create_charge` does not exist on the
installed SDK (2.4.1 exposes `create_payment`).
- Evidence: `probe_api` line 88; `python -c "import stripe; help(stripe.Charge)"`
- Repro: `pytest tests/test_billing.py::test_charge` → `AttributeError`
- Confidence: high

### F2 — MAJOR — `tests/test_billing.py:31` — assertion removed
...

## Not findings
<nits and taste, one line each. Optional.>

## Verdict
<Can this merge? BLOCK / MERGE WITH FIXES / MERGE. Conditions, in order.>
```

## Rules

- Order findings by severity, then by file.
- One finding, one location, one cause. Split compound ones.
- Every finding needs a repro or a probe line. Otherwise move it to a
  `## Suspected` section and name the missing evidence.
- Quote at most three lines of source. The reviewer will open the file.
- No severity inflation: `BLOCKER` means "merging ships a defect", not "I would
  have written it differently".
- The weakest useful report is 3 findings and a verdict. The weakest *useless*
  report is 25 findings and no verdict.
