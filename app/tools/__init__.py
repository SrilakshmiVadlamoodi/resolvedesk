"""Tool registry: each tool module exports NAME, SCHEMA, REQUIRES_CONFIRMATION, execute()."""

from app.tools import (
    escalate_to_human,
    file_warranty_claim,
    get_customer_orders,
    get_order_details,
    initiate_refund,
    search_kb,
    update_shipping_address,
)

_MODULES = [
    get_customer_orders,
    get_order_details,
    search_kb,
    initiate_refund,
    update_shipping_address,
    file_warranty_claim,
    escalate_to_human,
]

TOOLS = {module.NAME: module for module in _MODULES}
TOOL_SCHEMAS = [module.SCHEMA for module in _MODULES]
