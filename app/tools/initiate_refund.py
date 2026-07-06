"""Write tool: create a refund. Requires confirmation and a prior policy ALLOW."""

from app.models import Order, Refund

NAME = "initiate_refund"
REQUIRES_CONFIRMATION = True

SCHEMA = {
    "name": NAME,
    "description": "Initiate a refund for an order belonging to the current customer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "amount": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["order_id", "amount", "reason"],
    },
}


def execute(
    session,
    customer_id: int,
    order_id: int,
    amount: float,
    reason: str,
    conversation_id: int | None = None,
    **_kwargs,
) -> dict:
    order = session.query(Order).filter_by(id=order_id, customer_id=customer_id).one_or_none()
    if order is None:
        return {"error": "not_found"}

    refund = Refund(
        order_id=order.id,
        amount=amount,
        status="approved",
        initiated_by="agent",
        conversation_id=conversation_id,
    )
    session.add(refund)
    session.commit()

    return {"refund_id": refund.id, "amount": float(amount), "status": "approved"}
