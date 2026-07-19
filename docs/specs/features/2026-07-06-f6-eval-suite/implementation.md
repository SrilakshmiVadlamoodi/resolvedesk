# F-006 — Implementation Notes

## What was built

- **`evals/scenarios.py`** — `Scenario` dataclass + `load_scenarios(scenarios_dir, subset)`,
  loading `evals/scenarios/*.yaml`, sorted by id, filterable to `subset="smoke"`.
- **`evals/fixtures.py`** — `seed_eval_extras(session)`: three additional orders beyond
  the shared demo fixture (`data/seed.py:seed_domain`) that eval scenarios need but the
  shared fixture doesn't have: a window-expired delivery (16 days), a non-returnable
  category item (`earphones_opened`), and an out-for-delivery shipment. Kept separate
  from `seed_domain` so it never affects F-001 through F-005's shared demo data or tests.
- **`evals/runner.py`** — `run_scenario(scenario, llm_complete, session=None,
  customer_id=None)`: executes each turn (`user` message or `confirm`) against the real
  `agent.run_turn`/`confirm_action`, against a fresh seeded in-memory DB per scenario
  (or an injected session/customer_id for unit tests). Checks:
  - **State**: `must_not: [refund_created, address_updated, escalation_created]`
  - **Event**: `tools_called`, `policy_outcome` + `policy_reason` (any `policy_decision`
    event — covers both DENY and ESCALATE, since DENY never creates an `Escalation` row),
    `escalation_reason` (checked against `Escalation` rows)
  - **Answer**: `answer_contains_any` (case-insensitive substring)
  - **`api_round_trip`**: a non-empty final answer came back with no exception —
    the AC4 check, deliberately independent of any behavioral assertion.
  - Any exception raised during scenario execution (e.g. a real auth failure) is caught
    and recorded as a scenario failure, not allowed to crash the whole suite run.
- **`evals/suite.py`** — `run_suite(subset, scenarios_dir, llm_complete_factory)`
  (a *factory*, not a single shared callable, so each scenario gets its own fresh
  call-count state), `render_report`/`write_report` → `evals/report.md`
  (pass-rate summary, per-scenario pass/fail table, failure details with
  answer/tools-called/reason diffs).
- **`evals/run.py`** — `python -m evals.run [--subset smoke]`. Exit code 0 requires
  100% pass on `--subset smoke` (all demo-critical) or ≥90% on a full run; non-zero
  otherwise, so CI actually gates on this.
- **52 scenario files** in `evals/scenarios/` (spec's ~50 plus 2 dedicated
  `api_round_trip` checks): 15 happy, 10 policy edges, 8 escalation triggers, 8
  adversarial, 5 out-of-scope, 4 multi-turn, plus 2 real-API smoke checks. 8 total
  tagged `smoke: true`.

## Key decisions

- **`llm_complete_factory`, not a shared `llm_complete`.** Each scenario needs its own
  LLM call sequence; a single shared callable/iterator would bleed state across
  scenarios (scenario 2 could accidentally consume scenario 1's canned responses in
  tests, or — for the real path — there's no state to bleed since `llm.complete` is
  stateless, but the factory pattern makes both cases correct without special-casing).
- **`policy_reason` is a new expectation, not just `escalation_reason`.** F-003/F-004's
  policy engine returns DENY for absolute rules (non-returnable, already-shipped,
  use-cancellation) and only ESCALATE creates an `Escalation` row. Several of the 10
  policy-edge scenarios need to assert a DENY reason, which `escalation_reason` alone
  can't see — discovered this gap while writing `policy-03-non-returnable.yaml` and
  fixed it with a proper failing test first (`test_policy_reason_check_fails_when_actual_reason_differs`)
  before wiring the check in.
- **Fixed a real runner bug found while designing a multi-turn scenario**: the original
  implementation reset `pending_nonce` to `None` after *every* turn that didn't return a
  new `confirmation_request`, so a customer asking an unrelated question between "refund
  my order" and confirming would silently lose the pending confirmation. Fixed to only
  update `pending_nonce` when a new one is actually issued — this is a genuine agent-UX
  bug fix, not just an eval-scenario accommodation (`multi-turn-04-interjection-before-confirm.yaml`
  and its matching unit test both exercise it).
- **Two orders with matching product names would have been ambiguous** for scenarios
  and for a real model to disambiguate (`evals/fixtures.py` originally reused
  "VoltWatch Fit" for the out-for-delivery order, colliding with the shared fixture's
  existing VoltWatch order for the same customer). Changed the out-for-delivery fixture
  to use VoltPlug Mini instead, so every policy-edge scenario message unambiguously
  identifies one order.
- **`escalation-07-loop-safety-max-steps.yaml` is explicitly flagged as
  non-deterministic** in its own comment header — forcing exactly 6+ tool-call steps
  via natural conversation depends on how many calls the real model chooses to make,
  which can't be scripted deterministically. It's excluded from the smoke subset and
  documented as an acceptable candidate failure, not silently included as if it were
  reliable.

## What could NOT be verified in this environment

**No `ANTHROPIC_API_KEY` is configured in this sandbox**, so `python -m evals.run` (real
or `--subset smoke`) has not actually been executed against the live Claude API here.
Everything above the LLM boundary is genuinely tested (140/140 tests, including the
runner's assertion logic, the exception-safety wrapper, the report generation, and the
scenario/fixture loading) with a fake `llm_complete` — exactly the same boundary
discipline every other feature in this codebase uses. But:

- **AC1** (full suite runs unattended and produces a report) is verified structurally
  (the suite/report machinery works end-to-end against fake LLM responses) but not
  against the real API.
- **AC2** (3 consecutive smoke runs, no flakiness) and **AC3** (≥90% pass rate,
  documented accepted failures) require a real run this environment cannot perform.
- **AC4** (1-2 smoke scenarios prove a real API round-trip) — the scenarios and the
  `api_round_trip` check exist and are unit-tested, but have not been exercised against
  the real API.

**Action needed from you**: export a real `ANTHROPIC_API_KEY` and run
`uv run python -m evals.run --subset smoke` (fast/cheap) and then
`uv run python -m evals.run` (full, budget < ₹100 per spec) to actually produce
`evals/report.md` and confirm the live pass rate. I cannot do this from here — no key
is present in this session's environment.
