from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import policy
from app.db import Base
from app.models import Customer, Order, OrderItem, Product


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_order(
    session,
    status="delivered",
    delivered_days_ago=3,
    out_for_delivery=False,
    category="audio",
):
    customer = Customer(name="Test Customer", email=f"{id(object())}@example.com", phone="0000000000")
    session.add(customer)
    session.flush()

    product = Product(name="Test Product", category=category, price=2999, warranty_months=12)
    session.add(product)
    session.flush()

    now = datetime.now(timezone.utc)
    order = Order(
        customer_id=customer.id,
        status=status,
        total=2999,
        shipping_address="Test Address",
        placed_at=now - timedelta(days=delivered_days_ago + 2),
        delivered_at=(now - timedelta(days=delivered_days_ago)) if status == "delivered" else None,
        out_for_delivery=out_for_delivery,
    )
    session.add(order)
    session.flush()

    session.add(OrderItem(order_id=order.id, product_id=product.id, qty=1, price=product.price))
    session.commit()
    session.refresh(order)
    return order


def test_within_window_and_limit_allows():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=3)

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[])

    assert decision.outcome == "ALLOW"


def test_over_ceiling_escalates_with_over_limit_reason():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=3)

    decision = policy.check_refund(order, Decimal("6000"), existing_refunds=[])

    assert decision.outcome == "ESCALATE"
    assert decision.reason == "OVER_LIMIT"


def test_exactly_at_ceiling_allows():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=3)

    decision = policy.check_refund(order, Decimal("5000"), existing_refunds=[])

    assert decision.outcome == "ALLOW"


def test_day_11_after_delivery_escalates_with_window_expired_reason():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=11)

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[])

    assert decision.outcome == "ESCALATE"
    assert decision.reason == "WINDOW_EXPIRED"


def test_day_10_after_delivery_still_within_window():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=10)

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[])

    assert decision.outcome == "ALLOW"


def test_non_returnable_category_denies():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=3, category="earphones_opened")

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[])

    assert decision.outcome == "DENY"
    assert decision.reason == "NON_RETURNABLE"


def test_software_licenses_category_denies():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=3, category="software_licenses")

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[])

    assert decision.outcome == "DENY"
    assert decision.reason == "NON_RETURNABLE"


def test_duplicate_refund_escalates():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=3)

    class _ExistingRefund:
        pass

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[_ExistingRefund()])

    assert decision.outcome == "ESCALATE"
    assert decision.reason == "DUPLICATE"


def test_shipped_not_out_for_delivery_denies_pointing_to_cancellation():
    session = make_session()
    order = make_order(session, status="shipped", out_for_delivery=False)

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[])

    assert decision.outcome == "DENY"
    assert decision.reason == "USE_CANCELLATION"


def test_shipped_out_for_delivery_escalates():
    session = make_session()
    order = make_order(session, status="shipped", out_for_delivery=True)

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[])

    assert decision.outcome == "ESCALATE"
    assert decision.reason == "OUT_FOR_DELIVERY"


def test_duplicate_check_takes_priority_over_non_returnable():
    session = make_session()
    order = make_order(session, status="delivered", delivered_days_ago=3, category="earphones_opened")

    class _ExistingRefund:
        pass

    decision = policy.check_refund(order, Decimal("2000"), existing_refunds=[_ExistingRefund()])

    assert decision.outcome == "ESCALATE"
    assert decision.reason == "DUPLICATE"


def test_policy_constants_live_in_one_config_block():
    assert policy.REFUND_POLICY.auto_approve_ceiling == Decimal("5000")
    assert policy.REFUND_POLICY.return_window_days == 10
    assert "earphones_opened" in policy.REFUND_POLICY.non_returnable_categories
    assert "software_licenses" in policy.REFUND_POLICY.non_returnable_categories
