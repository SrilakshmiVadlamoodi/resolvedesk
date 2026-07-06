"""Policy engine. The LLM proposes actions; these pure functions dispose them.

check_refund encodes VoltKart's full refund ruleset (F-003) so the agent's
authority is bounded by code, not by prompt obedience. All tunable constants
live in REFUND_POLICY below — changing a limit is a one-line edit there.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from app.models import Order


@dataclass(frozen=True)
class RefundPolicyConfig:
    auto_approve_ceiling: Decimal = Decimal("5000")
    return_window_days: int = 10
    non_returnable_categories: frozenset[str] = field(
        default_factory=lambda: frozenset({"earphones_opened", "software_licenses"})
    )


REFUND_POLICY = RefundPolicyConfig()


@dataclass
class PolicyDecision:
    outcome: Literal["ALLOW", "DENY", "ESCALATE"]
    reason: str
    customer_message: str

    @property
    def allowed(self) -> bool:
        return self.outcome == "ALLOW"


def check_refund(order: Order, amount, existing_refunds: list) -> PolicyDecision:
    """Pure function: order + proposed amount + this order's existing refunds
    -> a decision. DENY = absolute rule; ESCALATE = a human could approve."""
    if existing_refunds:
        return PolicyDecision(
            "ESCALATE",
            "DUPLICATE",
            "There's already a refund on this order — I've flagged it for a human to review.",
        )

    categories = {item.product.category for item in order.items}
    if categories & REFUND_POLICY.non_returnable_categories:
        return PolicyDecision(
            "DENY",
            "NON_RETURNABLE",
            "This item's category isn't eligible for refund, but I can escalate if you'd like a human to take a look.",
        )

    if order.status == "shipped":
        if order.out_for_delivery:
            return PolicyDecision(
                "ESCALATE",
                "OUT_FOR_DELIVERY",
                "Your order is already out for delivery — I've flagged this for a human to intercept it.",
            )
        return PolicyDecision(
            "DENY",
            "USE_CANCELLATION",
            "This order hasn't been delivered yet, so I can't refund it — I can cancel it for you instead.",
        )

    if order.status != "delivered" or order.delivered_at is None:
        return PolicyDecision(
            "ESCALATE",
            "NOT_DELIVERED",
            "I can't confirm this order's delivery status — I've flagged it for a human to check.",
        )

    delivered_at = order.delivered_at
    if delivered_at.tzinfo is None:
        delivered_at = delivered_at.replace(tzinfo=timezone.utc)
    days_since_delivery = (_now() - delivered_at).days
    if days_since_delivery > REFUND_POLICY.return_window_days:
        return PolicyDecision(
            "ESCALATE",
            "WINDOW_EXPIRED",
            "It's been more than 10 days since delivery — I've flagged this for a human to review.",
        )

    if amount > REFUND_POLICY.auto_approve_ceiling:
        return PolicyDecision(
            "ESCALATE",
            "OVER_LIMIT",
            "This refund amount needs a human's sign-off — I've flagged it for review.",
        )

    return PolicyDecision("ALLOW", "WITHIN_POLICY", "Your refund has been approved.")


def check_address_change(order: Order) -> PolicyDecision:
    if order.status != "placed":
        return PolicyDecision(
            "DENY",
            "ALREADY_SHIPPED",
            "This order has already shipped, so I can't change the address anymore.",
        )
    return PolicyDecision("ALLOW", "NOT_YET_SHIPPED", "Address updated.")


def check(tool_name: str, arguments: dict, session, customer_id: int) -> PolicyDecision:
    """Dispatch a policy check for a tool call. Read/control tools are always
    ALLOW — only tools that mutate state are gated."""
    if tool_name == "initiate_refund":
        order = (
            session.query(Order)
            .filter_by(id=arguments["order_id"], customer_id=customer_id)
            .one_or_none()
        )
        if order is None:
            return PolicyDecision("DENY", "NOT_FOUND", "I can't find that order.")
        return check_refund(order, arguments["amount"], list(order.refunds))

    if tool_name == "update_shipping_address":
        order = (
            session.query(Order)
            .filter_by(id=arguments["order_id"], customer_id=customer_id)
            .one_or_none()
        )
        if order is None:
            return PolicyDecision("DENY", "NOT_FOUND", "I can't find that order.")
        return check_address_change(order)

    return PolicyDecision("ALLOW", "DEFAULT_ALLOW", "")


def _now() -> datetime:
    return datetime.now(timezone.utc)
