"""Write tool: update an order's shipping address. Only valid before shipment."""

from app.models import Order

NAME = "update_shipping_address"
REQUIRES_CONFIRMATION = True

SCHEMA = {
    "name": NAME,
    "description": "Update the shipping address of an order that hasn't shipped yet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "new_address": {"type": "string"},
        },
        "required": ["order_id", "new_address"],
    },
}


def execute(session, customer_id: int, order_id: int, new_address: str, **_kwargs) -> dict:
    order = session.query(Order).filter_by(id=order_id, customer_id=customer_id).one_or_none()
    if order is None:
        return {"error": "not_found"}
    if order.status != "placed":
        return {"error": "already_shipped"}

    order.shipping_address = new_address
    session.commit()

    return {"order_id": order.id, "new_address": new_address, "status": "updated"}
