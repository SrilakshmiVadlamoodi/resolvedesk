# F-003 — Refund Policy Engine

## Goal
Encode VoltKart's refund rules as deterministic Python so the agent's authority is bounded by code, not by prompt obedience.

## VoltKart refund policy (also written as the KB doc, so code and KB agree)
- Full refund if: order delivered within the last **10 days**, item not marked non-returnable.
- Auto-approve ceiling: **₹5,000** per order; above that → escalate to human.
- One auto-refund per order (idempotency + abuse guard); second attempt → escalate.
- Undelivered-but-shipped orders: refund only via cancellation path if not yet out for delivery; else escalate.
- Categories `earphones_opened`, `software_licenses`: non-refundable → polite decline citing KB, offer escalation.

## Interface
```python
@dataclass
class PolicyDecision:
    outcome: Literal["ALLOW", "DENY", "ESCALATE"]
    reason: str            # machine-readable code, e.g. OVER_LIMIT, WINDOW_EXPIRED
    customer_message: str  # plain-language explanation the agent can relay

def check_refund(order: Order, amount: Decimal, existing_refunds: list[Refund]) -> PolicyDecision
def check_address_change(order: Order) -> PolicyDecision   # only before "shipped"
```
- Pure functions, no I/O → trivially unit-testable.
- Every decision logs a `policy_decision` event.
- DENY vs ESCALATE: DENY = rule is absolute (non-returnable category); ESCALATE = a human *could* approve (over limit, expired window with sympathetic story).

## Acceptance criteria
1. Unit tests cover: within window/limit → ALLOW; over ₹5,000 → ESCALATE(OVER_LIMIT); day 11 → ESCALATE(WINDOW_EXPIRED); non-returnable → DENY; duplicate refund → ESCALATE(DUPLICATE).
2. No code path executes a refund without a prior ALLOW event for that exact (order, amount).
3. Policy constants live in one config block — changing the ceiling is a one-line edit.

## Out of scope
Partial/item-level refunds, store credit, ML-based fraud scoring.
