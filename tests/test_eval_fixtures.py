from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Customer, Order, OrderItem
from data.seed import seed_domain, seed_kb
from evals.fixtures import seed_eval_extras


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    return session


def test_seed_eval_extras_adds_window_expired_non_returnable_and_out_for_delivery_orders():
    session = make_session()

    seed_eval_extras(session)

    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    orders = session.query(Order).filter_by(customer_id=aditi.id).all()

    window_expired = [o for o in orders if o.status == "delivered" and (o.delivered_at is not None)]
    assert any(o.total == 1999 for o in orders)  # window-expired order
    assert any(o.total == 2499 for o in orders)  # non-returnable order
    assert any(o.status == "shipped" and o.out_for_delivery for o in orders)  # out-for-delivery order
    assert window_expired  # sanity: at least one delivered order exists


def test_seed_eval_extras_non_returnable_order_has_earphones_opened_category():
    session = make_session()
    seed_eval_extras(session)

    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    nonreturnable_order = session.query(Order).filter_by(customer_id=aditi.id, total=2499).one()
    item = session.query(OrderItem).filter_by(order_id=nonreturnable_order.id).one()

    assert item.product.category == "earphones_opened"
