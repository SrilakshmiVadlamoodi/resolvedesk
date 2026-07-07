"""Reproducible demo database. Run: python -m data.seed"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db import Base, engine, get_session
from app.models import (
    Conversation,
    Customer,
    Escalation,
    Event,
    KBChunk,
    KBDoc,
    Message,
    Order,
    OrderItem,
    PendingAction,
    Product,
    Refund,
)
from app.rag import chunk_markdown, embed_texts

KB_DIR = Path(__file__).parent / "kb"


def _title_from_markdown(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


def seed_kb(session) -> None:
    """Rebuild kb_docs/kb_chunks from data/kb/*.md. Safe to rerun — clears
    existing rows first so re-seeding never duplicates or drifts."""
    session.query(KBChunk).delete()
    session.query(KBDoc).delete()
    session.commit()

    for path in sorted(KB_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        doc = KBDoc(slug=path.stem, title=_title_from_markdown(text))
        session.add(doc)
        session.flush()

        chunks = chunk_markdown(text)
        if not chunks:
            continue
        vectors = embed_texts([c.text for c in chunks])
        for chunk, vector in zip(chunks, vectors):
            session.add(
                KBChunk(
                    doc_id=doc.id,
                    section=chunk.section,
                    text=chunk.text,
                    embedding=vector.astype("float32").tobytes(),
                )
            )
    session.commit()


def seed_domain(session) -> None:
    """Rebuild customers/products/orders/order_items/refunds with a small,
    reproducible VoltKart demo fixture. Safe to rerun."""
    session.query(Refund).delete()
    session.query(OrderItem).delete()
    session.query(Order).delete()
    session.query(Product).delete()
    session.query(Customer).delete()
    session.commit()

    now = datetime.now(timezone.utc)

    aditi = Customer(name="Aditi Rao", email="aditi@example.com", phone="9876543210")
    rahul = Customer(name="Rahul Shah", email="rahul@example.com", phone="9876500000")
    session.add_all([aditi, rahul])
    session.flush()

    earbuds = Product(name="VoltBuds Pro", category="audio", price=2999, warranty_months=12)
    watch = Product(name="VoltWatch Fit", category="wearables", price=5999, warranty_months=12)
    plug = Product(name="VoltPlug Mini", category="smart_home", price=999, warranty_months=18)
    session.add_all([earbuds, watch, plug])
    session.flush()

    delivered_order = Order(
        customer_id=aditi.id,
        status="delivered",
        total=earbuds.price,
        shipping_address="12 MG Road, Bengaluru",
        placed_at=now - timedelta(days=5),
        delivered_at=now - timedelta(days=3),
    )
    shipped_order = Order(
        customer_id=aditi.id,
        status="shipped",
        total=watch.price,
        shipping_address="12 MG Road, Bengaluru",
        placed_at=now - timedelta(days=2),
    )
    other_customer_order = Order(
        customer_id=rahul.id,
        status="placed",
        total=plug.price,
        shipping_address="7 Park Street, Kolkata",
        placed_at=now - timedelta(hours=6),
    )
    session.add_all([delivered_order, shipped_order, other_customer_order])
    session.flush()

    session.add_all(
        [
            OrderItem(order_id=delivered_order.id, product_id=earbuds.id, qty=1, price=earbuds.price),
            OrderItem(order_id=shipped_order.id, product_id=watch.id, qty=1, price=watch.price),
            OrderItem(order_id=other_customer_order.id, product_id=plug.id, qty=1, price=plug.price),
        ]
    )
    session.commit()


_SAMPLE_CONVERSATIONS = [
    # (status, intent, user_message, tool_call, escalation_reason)
    ("resolved", "order_status", "Where is my order?", ("get_customer_orders", {}, {"orders": []}), None),
    ("resolved", "order_status", "What's the status of order 1?", ("get_order_details", {"order_id": 1}, {"status": "delivered"}), None),
    ("resolved", "product_question", "Do the earbuds have noise cancellation?", None, None),
    ("resolved", "refund", "I'd like a refund on my earbuds", ("initiate_refund", {"order_id": 1, "amount": 1500, "reason": "changed mind"}, {"refund_id": 101, "amount": 1500, "status": "approved"}), None),
    ("resolved", "refund", "Refund my smart plug please", ("initiate_refund", {"order_id": 3, "amount": 999, "reason": "wrong item"}, {"refund_id": 102, "amount": 999, "status": "approved"}), None),
    ("resolved", "warranty", "My watch won't turn on, still under warranty", ("file_warranty_claim", {"order_id": 2, "product_id": 2, "issue": "won't power on"}, {"status": "claim_filed"}), None),
    ("resolved", "other", "Do you have a loyalty program?", None, None),
    ("resolved", "product_question", "What's your shipping policy?", ("search_kb", {"query": "shipping policy"}, {"chunks": [], "low_confidence": False}), None),
    ("escalated", "refund", "Refund my ₹8,999 order", ("initiate_refund", {"order_id": 4, "amount": 8999, "reason": "too expensive"}, None), "OVER_LIMIT"),
    ("escalated", "refund", "It's been 15 days but I want a refund", ("initiate_refund", {"order_id": 5, "amount": 1200, "reason": "late refund request"}, None), "WINDOW_EXPIRED"),
    ("escalated", "refund", "I already got a refund but want another", ("initiate_refund", {"order_id": 6, "amount": 500, "reason": "duplicate"}, None), "DUPLICATE"),
    ("escalated", "other", "I want to talk to a human right now", None, "HUMAN_REQUESTED"),
    ("escalated", "product_question", "Do you sell industrial generators?", ("search_kb", {"query": "industrial generators"}, {"chunks": [], "low_confidence": True}), "LOW_CONFIDENCE"),
    ("escalated", "other", "Can you help me with something complicated", None, "MAX_STEPS_EXCEEDED"),
    ("escalated", "warranty", "My order arrived damaged and support won't help", None, "HUMAN_REQUESTED"),
]


def seed_admin_demo_data(session) -> None:
    """~15 synthetic completed conversations so the admin dashboard (F-005)
    looks alive on first load. Clearly sample data — surfaced as such in the
    UI, per spec.md. Safe to rerun."""
    session.query(Escalation).delete()
    session.query(PendingAction).delete()
    session.query(Event).delete()
    session.query(Message).delete()
    session.query(Conversation).delete()
    session.commit()

    for status, intent_label, user_message, tool_call, escalation_reason in _SAMPLE_CONVERSATIONS:
        conversation = Conversation(customer_id=None, status=status)
        session.add(conversation)
        session.flush()

        session.add(Message(conversation_id=conversation.id, role="user", content=user_message))
        session.add(
            Event(
                conversation_id=conversation.id,
                type="retrieval",
                payload={"query": user_message, "chunk_ids": [], "scores": []},
            )
        )

        if tool_call is not None:
            tool_name, arguments, result = tool_call
            if result is not None:
                session.add(
                    Event(
                        conversation_id=conversation.id,
                        type="tool_call",
                        payload={"tool": tool_name, "arguments": arguments, "result": result},
                    )
                )
            if escalation_reason and tool_name in ("initiate_refund", "update_shipping_address"):
                session.add(
                    Event(
                        conversation_id=conversation.id,
                        type="policy_decision",
                        payload={
                            "tool": tool_name,
                            "arguments": arguments,
                            "outcome": "ESCALATE",
                            "reason": escalation_reason,
                        },
                    )
                )

        if status == "escalated":
            escalation_row = Escalation(
                conversation_id=conversation.id,
                reason=escalation_reason,
                summary=f"Sample escalation for demo purposes: {user_message}",
                sentiment="neutral",
                attempted_actions=[tool_call[0]] if tool_call else [],
                suggested_action="Review manually (sample data).",
                status="open",
            )
            session.add(escalation_row)
            session.flush()
            session.add(
                Event(
                    conversation_id=conversation.id,
                    type="escalation",
                    payload={"escalation_id": escalation_row.id, "reference": f"E-{escalation_row.id}", "reason": escalation_reason},
                )
            )
            session.add(Message(conversation_id=conversation.id, role="assistant", content="I've raised this with our support team."))
        else:
            session.add(Message(conversation_id=conversation.id, role="assistant", content="Happy to help — resolved."))

        session.add(Event(conversation_id=conversation.id, type="intent", payload={"intent": intent_label}))

    session.commit()


def main() -> None:
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        seed_kb(session)
        seed_domain(session)
        seed_admin_demo_data(session)
        doc_count = session.query(KBDoc).count()
        chunk_count = session.query(KBChunk).count()
        order_count = session.query(Order).count()
        conversation_count = session.query(Conversation).count()
        print(
            f"Seeded {chunk_count} KB chunks from {doc_count} docs, {order_count} orders, "
            f"{conversation_count} sample conversations."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
