# F-003 — Validation Record

## Automated tests

`uv run pytest tests/ -v` — 53/53 passed (F-001+F-002's 40, plus 13 new: 12 in
`test_refund_policy.py` and one added to `test_agent.py`; 2 pre-existing
`test_policy.py` refund tests updated to use real `Order` fixtures instead of
`order=None`, since the provisional stub they exercised no longer exists).
`uv run ruff check app data tests` — all checks passed.

| File | Covers |
|---|---|
| `tests/test_refund_policy.py` | every branch of the new `check_refund` ruleset, boundary conditions, and the single-config-block requirement |
| `tests/test_policy.py` | `check_refund`/`check_address_change`/`check()` dispatch (updated for the new signature) |
| `tests/test_agent.py` | non-returnable-category refund denied end-to-end, no `Refund` row created |

## Acceptance criteria (from spec.md)

**1. Unit tests cover: within window/limit → ALLOW; over ₹5,000 → ESCALATE(OVER_LIMIT); day 11 → ESCALATE(WINDOW_EXPIRED); non-returnable → DENY; duplicate refund → ESCALATE(DUPLICATE).**

PASS — all five named cases plus boundary cases (day 10 still within window, exactly
₹5,000 still allowed) and the undelivered-but-shipped branch:

- `test_within_window_and_limit_allows` — ALLOW
- `test_over_ceiling_escalates_with_over_limit_reason` — ESCALATE(OVER_LIMIT)
- `test_exactly_at_ceiling_allows` — boundary, ALLOW at exactly ₹5,000
- `test_day_11_after_delivery_escalates_with_window_expired_reason` — ESCALATE(WINDOW_EXPIRED)
- `test_day_10_after_delivery_still_within_window` — boundary, ALLOW at day 10
- `test_non_returnable_category_denies` / `test_software_licenses_category_denies` — DENY(NON_RETURNABLE)
- `test_duplicate_refund_escalates` — ESCALATE(DUPLICATE)
- `test_duplicate_check_takes_priority_over_non_returnable` — priority ordering
- `test_shipped_not_out_for_delivery_denies_pointing_to_cancellation` / `test_shipped_out_for_delivery_escalates` — undelivered-but-shipped branch

**2. No code path executes a refund without a prior ALLOW event for that exact (order, amount).**

PASS — `app/agent.py`'s loop only proceeds to confirmation/execution when
`decision.outcome` is neither `ESCALATE` nor `DENY` (i.e., `ALLOW`); both non-ALLOW
branches `return`/`continue` before reaching the tool. Verified end-to-end by
`test_prompt_injected_large_refund_is_escalated_not_executed` (F-002, ESCALATE case)
and the new `test_non_returnable_category_refund_is_denied_not_executed` (DENY case) —
both assert zero `Refund` rows exist afterward.

**3. Policy constants live in one config block — changing the ceiling is a one-line edit.**

PASS — `RefundPolicyConfig` (frozen dataclass) instantiated once as `REFUND_POLICY`;
`test_policy_constants_live_in_one_config_block` asserts the ceiling, window, and
non-returnable set all come from that single object.

## Out-of-scope check

No partial/item-level refunds, no store credit, no ML-based fraud scoring —
`check_refund` operates on the full order/amount only, and `DUPLICATE` is a simple
existing-refunds-not-empty check, not a scored risk model.

## Verdict

3/3 acceptance criteria PASS. Feature complete per spec.
