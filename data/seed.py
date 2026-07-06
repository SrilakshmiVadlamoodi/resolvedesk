"""Reproducible demo database. Run: python -m data.seed"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db import Base, engine, get_session
from app.models import Customer, KBChunk, KBDoc, Order, OrderItem, Product, Refund
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


def main() -> None:
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        seed_kb(session)
        seed_domain(session)
        doc_count = session.query(KBDoc).count()
        chunk_count = session.query(KBChunk).count()
        order_count = session.query(Order).count()
        print(f"Seeded {chunk_count} KB chunks from {doc_count} docs, {order_count} orders.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
