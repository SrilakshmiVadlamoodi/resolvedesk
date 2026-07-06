from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Customer, Order, Product
from data.seed import seed_domain


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_seed_domain_populates_customers_products_orders():
    session = make_session()

    seed_domain(session)

    assert session.query(Customer).count() >= 2
    assert session.query(Product).count() >= 3
    assert session.query(Order).count() >= 3
    # at least one delivered order under the refund ceiling, for refund-flow tests
    assert (
        session.query(Order).filter_by(status="delivered").count() >= 1
    )


def test_seed_domain_is_idempotent_on_rerun():
    session = make_session()

    seed_domain(session)
    first_customers = session.query(Customer).count()
    first_orders = session.query(Order).count()

    seed_domain(session)
    second_customers = session.query(Customer).count()
    second_orders = session.query(Order).count()

    assert second_customers == first_customers
    assert second_orders == first_orders


def test_seed_domain_orders_belong_to_different_customers():
    session = make_session()

    seed_domain(session)

    customer_ids = {order.customer_id for order in session.query(Order).all()}
    assert len(customer_ids) >= 2
