"""Read tool: fetch one order's details, scoped to the requesting customer.

customer_id always comes from the server-side session, never from LLM
arguments, so this can't be used to look up another customer's order.
"""

from app.models import Order

NAME = "get_order_details"
REQUIRES_CONFIRMATION = False

SCHEMA = {
    "name": NAME,
    "description": "Get details of a specific order by ID, for the current customer.",
    "input_schema": {
        "type": "object",
        "properties": {"order_id": {"type": "integer"}},
        "required": ["order_id"],
    },
}


def execute(session, customer_id: int, order_id: int, **_kwargs) -> dict:
    order = session.query(Order).filter_by(id=order_id, customer_id=customer_id).one_or_none()
    if order is None:
        return {"error": "not_found"}

    return {
        "id": order.id,
        "status": order.status,
        "total": float(order.total),
        "shipping_address": order.shipping_address,
        "placed_at": order.placed_at.isoformat(),
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
    }
