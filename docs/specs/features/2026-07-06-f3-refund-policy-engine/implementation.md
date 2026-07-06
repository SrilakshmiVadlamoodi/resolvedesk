# F-003 — Implementation Notes

## What was built

- **`app/policy.py:check_refund`** replaced F-002's provisional ceiling-only stub with
  the full VoltKart refund ruleset, in priority order:
  1. Existing refund on the order → `ESCALATE(DUPLICATE)` (abuse guard, checked first —
     absolute regardless of any other fact about the order).
  2. Any order item in a non-returnable category (`earphones_opened`,
     `software_licenses`) → `DENY(NON_RETURNABLE)`.
  3. Order `shipped` but not yet delivered: `out_for_delivery=False` →
     `DENY(USE_CANCELLATION)` (wrong tool — direct to cancellation); `True` →
     `ESCALATE(OUT_FOR_DELIVERY)` (a human could still intercept it).
  4. Not `delivered` (or missing `delivered_at`) → `ESCALATE(NOT_DELIVERED)`.
  5. More than 10 days since delivery → `ESCALATE(WINDOW_EXPIRED)`.
  6. Amount over ₹5,000 → `ESCALATE(OVER_LIMIT)`.
  7. Otherwise → `ALLOW(WITHIN_POLICY)`.
- **`RefundPolicyConfig`** (frozen dataclass) — `auto_approve_ceiling` (₹5,000),
  `return_window_days` (10), `non_returnable_categories`. Instantiated once as
  `REFUND_POLICY`, the single block satisfying AC3 ("changing the ceiling is a
  one-line edit").
- **`Order.out_for_delivery`** (new `Boolean` column, default `False`) — the model
  didn't previously distinguish "shipped" from "shipped and now out for delivery,"
  which the spec's undelivered-but-shipped rule needs.
- `check_address_change` and the `check()` dispatcher are unchanged from F-002 — the
  spec's interface (`PolicyDecision(outcome, reason, customer_message)`,
  `check_refund(order, amount, existing_refunds)`, `check_address_change(order)`) was
  already in place, so this was a body replacement, not a contract change.

## Key decisions

- **Priority order matters and is deliberate**, not incidental: duplicate-refund and
  non-returnable are absolute rules checked before anything that depends on order
  state (shipment/delivery/window/amount), so e.g. a non-returnable item with an
  existing refund still reports `DUPLICATE` (the stricter abuse guard), not
  `NON_RETURNABLE` — verified by
  `test_duplicate_check_takes_priority_over_non_returnable`.
- **Window boundary is inclusive of day 10, exclusive of day 11** — `days_since_delivery
  > 10` is the escalate condition, matching AC1's literal "day 11 → ESCALATE" example.
  Ceiling boundary is inclusive at exactly ₹5,000 (`amount > ceiling`, not `>=`) — F-002's
  ceiling used `>=`; F-003's spec explicitly reads "above that," so `>` is correct here
  and F-002's version is now superseded.
- **SQLite strips tzinfo on datetime round-trip** — `check_refund` normalizes
  `order.delivered_at` to UTC-aware before subtracting from `_now()` if it comes back
  naive, rather than assuming the DB driver preserves timezone info.
- **`USE_CANCELLATION` vs `OUT_FOR_DELIVERY`**: the spec says "refund only via
  cancellation path if not yet out for delivery; else escalate" — read as: not-yet-out
  is a routing problem (wrong tool, hence `DENY`, not a human judgment call), while
  already-out-for-delivery genuinely needs a human's discretion (`ESCALATE`).

## Deviations from spec

None — `check_refund`/`check_address_change` signatures match spec.md's interface
exactly.

## Follow-ups (not blocking F-003)

- No demo fixture in `seed_domain` currently has a non-returnable category, a
  duplicate refund, or `out_for_delivery=True` — those paths are covered by unit tests
  constructing orders directly, not by the shared seed data. Worth adding one of each
  to `data/seed.py` if F-006's eval suite wants to exercise them through the full chat
  flow rather than at the policy-function level.
