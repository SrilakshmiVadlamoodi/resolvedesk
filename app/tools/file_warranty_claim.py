"""Write tool: file a warranty claim. Fulfillment is a manual step outside chat."""

from app.models import Order

NAME = "file_warranty_claim"
REQUIRES_CONFIRMATION = True

SCHEMA = {
    "name": NAME,
    "description": "File a warranty claim for a product on one of the customer's orders.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "product_id": {"type": "integer"},
            "issue": {"type": "string"},
        },
        "required": ["order_id", "product_id", "issue"],
    },
}


def execute(session, customer_id: int, order_id: int, product_id: int, issue: str, **_kwargs) -> dict:
    order = session.query(Order).filter_by(id=order_id, customer_id=customer_id).one_or_none()
    if order is None:
        return {"error": "not_found"}

    return {
        "order_id": order.id,
        "product_id": product_id,
        "issue": issue,
        "status": "claim_filed",
    }
