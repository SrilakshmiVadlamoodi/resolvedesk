from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Customer, Order, Refund
from app.tools import escalate_to_human, file_warranty_claim, initiate_refund, update_shipping_address
from data.seed import seed_domain


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_initiate_refund_creates_a_refund_row_for_the_owning_customer():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    result = initiate_refund.execute(
        session=session, customer_id=aditi.id, order_id=order.id, amount=2999, reason="changed mind"
    )

    assert result["status"] == "approved"
    assert session.query(Refund).filter_by(order_id=order.id).count() == 1


def test_initiate_refund_rejects_another_customers_order():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    rahul_order = session.query(Order).join(Customer).filter(Customer.email == "rahul@example.com").one()

    result = initiate_refund.execute(
        session=session, customer_id=aditi.id, order_id=rahul_order.id, amount=100, reason="x"
    )

    assert result == {"error": "not_found"}
    assert session.query(Refund).count() == 0


def test_update_shipping_address_updates_placed_order():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = Order(customer_id=aditi.id, status="placed", total=100, shipping_address="old")
    session.add(order)
    session.commit()

    result = update_shipping_address.execute(
        session=session, customer_id=aditi.id, order_id=order.id, new_address="new address"
    )

    assert result["status"] == "updated"
    session.refresh(order)
    assert order.shipping_address == "new address"


def test_update_shipping_address_refuses_after_shipment():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="shipped").one()

    result = update_shipping_address.execute(
        session=session, customer_id=aditi.id, order_id=order.id, new_address="new address"
    )

    assert result == {"error": "already_shipped"}


def test_file_warranty_claim_logs_a_claim():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    result = file_warranty_claim.execute(
        session=session, customer_id=aditi.id, order_id=order.id, product_id=1, issue="won't turn on"
    )

    assert result["status"] == "claim_filed"


def test_escalate_to_human_returns_escalated_status():
    session = make_session()

    result = escalate_to_human.execute(
        session=session, customer_id=1, reason="angry_customer", summary="Customer is upset about delay"
    )

    assert result["status"] == "escalated"
    assert result["reason"] == "angry_customer"
