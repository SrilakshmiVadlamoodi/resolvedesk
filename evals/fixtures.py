"""Extra order/product fixtures for eval scenarios that need policy edge
cases the shared demo seed (data/seed.py:seed_domain) doesn't include:
a window-expired delivery, a non-returnable category, and an
out-for-delivery shipment. Kept separate from seed_domain so it never
affects the shared demo DB other features/tests rely on."""

from datetime import datetime, timedelta, timezone

from app.models import Customer, Order, OrderItem, Product


def seed_eval_extras(session) -> None:
    now = datetime.now(timezone.utc)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    earbuds = session.query(Product).filter_by(name="VoltBuds Pro").one()
    plug = session.query(Product).filter_by(name="VoltPlug Mini").one()

    opened_earphones = Product(
        name="VoltBuds Pro (Opened Box)", category="earphones_opened", price=2499, warranty_months=0
    )
    # Delivered + within the return window + priced above the ₹5,000 auto-approve
    # ceiling is the only order state that reaches check_refund's OVER_LIMIT branch
    # (app/policy.py) — a shipped-not-delivered order hits the earlier
    # USE_CANCELLATION branch first, regardless of amount, which is why the
    # over-limit scenarios must not reuse the shared VoltWatch Fit (shipped) order.
    premium_speaker = Product(
        name="VoltSound Max", category="audio", price=6499, warranty_months=12
    )
    session.add_all([opened_earphones, premium_speaker])
    session.flush()

    window_expired_order = Order(
        customer_id=aditi.id,
        status="delivered",
        total=1999,
        shipping_address="12 MG Road, Bengaluru",
        placed_at=now - timedelta(days=20),
        delivered_at=now - timedelta(days=16),
    )
    nonreturnable_order = Order(
        customer_id=aditi.id,
        status="delivered",
        total=2499,
        shipping_address="12 MG Road, Bengaluru",
        placed_at=now - timedelta(days=5),
        delivered_at=now - timedelta(days=3),
    )
    out_for_delivery_order = Order(
        customer_id=aditi.id,
        status="shipped",
        total=999,
        shipping_address="12 MG Road, Bengaluru",
        placed_at=now - timedelta(days=1),
        out_for_delivery=True,
    )
    over_limit_order = Order(
        customer_id=aditi.id,
        status="delivered",
        total=6499,
        shipping_address="12 MG Road, Bengaluru",
        placed_at=now - timedelta(days=5),
        delivered_at=now - timedelta(days=3),
    )
    session.add_all([window_expired_order, nonreturnable_order, out_for_delivery_order, over_limit_order])
    session.flush()

    session.add_all(
        [
            OrderItem(order_id=window_expired_order.id, product_id=earbuds.id, qty=1, price=1999),
            OrderItem(order_id=nonreturnable_order.id, product_id=opened_earphones.id, qty=1, price=2499),
            OrderItem(order_id=out_for_delivery_order.id, product_id=plug.id, qty=1, price=999),
            OrderItem(order_id=over_limit_order.id, product_id=premium_speaker.id, qty=1, price=6499),
        ]
    )
    session.commit()
