from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import policy
from app.db import Base
from app.models import Customer, Order
from data.seed import seed_domain


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_check_refund_allows_within_ceiling():
    session = make_session()
    seed_domain(session)
    order = session.query(Order).filter_by(status="delivered").one()

    decision = policy.check_refund(order, 2999, existing_refunds=[])

    assert decision.outcome == "ALLOW"


def test_check_refund_escalates_over_ceiling():
    session = make_session()
    seed_domain(session)
    order = session.query(Order).filter_by(status="delivered").one()

    decision_context = policy.check_refund(order, 50000, existing_refunds=[])

    assert decision_context.outcome == "ESCALATE"
    assert decision_context.reason == "OVER_LIMIT"


def test_check_refund_escalates_on_duplicate():
    session = make_session()
    seed_domain(session)
    order = session.query(Order).filter_by(status="delivered").one()

    class FakeRefund:
        pass

    decision = policy.check_refund(order, 100, existing_refunds=[FakeRefund()])

    assert decision.outcome == "ESCALATE"
    assert decision.reason == "DUPLICATE"


def test_check_address_change_allows_before_shipment():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    placed_order = Order(customer_id=aditi.id, status="placed", total=100, shipping_address="x")
    session.add(placed_order)
    session.commit()

    decision = policy.check_address_change(placed_order)

    assert decision.outcome == "ALLOW"


def test_check_address_change_denies_after_shipment():
    session = make_session()
    seed_domain(session)
    shipped_order = session.query(Order).filter_by(status="shipped").one()

    decision = policy.check_address_change(shipped_order)

    assert decision.outcome == "DENY"
    assert decision.reason == "ALREADY_SHIPPED"


def test_check_dispatches_refund_and_scopes_to_customer():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    rahul_order = session.query(Order).join(Customer).filter(Customer.email == "rahul@example.com").one()

    decision = policy.check(
        "initiate_refund",
        {"order_id": rahul_order.id, "amount": 100, "reason": "test"},
        session,
        aditi.id,
    )

    assert decision.outcome == "DENY"
    assert decision.reason == "NOT_FOUND"


def test_check_defaults_to_allow_for_read_tools():
    session = make_session()

    decision = policy.check("get_customer_orders", {}, session, customer_id=1)

    assert decision.outcome == "ALLOW"
