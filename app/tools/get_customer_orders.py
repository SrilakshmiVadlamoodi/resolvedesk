"""Read tool: list the requesting customer's own orders."""

from app.models import Order

NAME = "get_customer_orders"
REQUIRES_CONFIRMATION = False

SCHEMA = {
    "name": NAME,
    "description": "List all orders belonging to the current customer.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}


def execute(session, customer_id: int, **_kwargs) -> dict:
    orders = session.query(Order).filter_by(customer_id=customer_id).all()
    return {
        "orders": [
            {
                "id": o.id,
                "customer_id": o.customer_id,
                "status": o.status,
                "total": float(o.total),
                "placed_at": o.placed_at.isoformat(),
            }
            for o in orders
        ]
    }
