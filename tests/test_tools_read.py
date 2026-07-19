from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Customer, Order
from app.tools import get_customer_orders, get_order_details, search_kb
from data.seed import seed_domain, seed_kb


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_get_customer_orders_returns_only_that_customers_orders():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()

    result = get_customer_orders.execute(session=session, customer_id=aditi.id)

    assert len(result["orders"]) == 2
    assert all(o["customer_id"] == aditi.id for o in result["orders"])


def test_get_customer_orders_includes_item_product_names():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()

    result = get_customer_orders.execute(session=session, customer_id=aditi.id)

    delivered_order = next(o for o in result["orders"] if o["status"] == "delivered")
    assert delivered_order["items"] == [{"product_name": "VoltBuds Pro", "qty": 1}]


def test_get_order_details_returns_order_for_owner():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    result = get_order_details.execute(session=session, customer_id=aditi.id, order_id=order.id)

    assert result["status"] == "delivered"
    assert result["total"] == 2999
    assert result["items"] == [{"product_name": "VoltBuds Pro", "qty": 1}]


def test_get_order_details_scopes_to_requesting_customer():
    session = make_session()
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    rahul_order = session.query(Order).join(Customer).filter(Customer.email == "rahul@example.com").one()

    result = get_order_details.execute(session=session, customer_id=aditi.id, order_id=rahul_order.id)

    assert result == {"error": "not_found"}


def test_search_kb_returns_ranked_chunks():
    session = make_session()
    seed_kb(session)

    result = search_kb.execute(session=session, customer_id=1, query="What's your refund window?")

    assert result["chunks"]
    assert result["chunks"][0]["section"] == "Refund window"
