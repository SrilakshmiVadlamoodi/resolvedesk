from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Conversation, Escalation, Event
from data.seed import seed_admin_demo_data, seed_domain, seed_kb


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    return session


def test_seed_admin_demo_data_creates_around_15_conversations():
    session = make_session()

    seed_admin_demo_data(session)

    assert session.query(Conversation).count() >= 15


def test_seed_admin_demo_data_includes_a_mix_of_resolved_and_escalated():
    session = make_session()

    seed_admin_demo_data(session)

    statuses = {c.status for c in session.query(Conversation).all()}
    assert "resolved" in statuses
    assert "escalated" in statuses


def test_seed_admin_demo_data_escalated_conversations_have_escalation_rows():
    session = make_session()

    seed_admin_demo_data(session)

    escalated_count = session.query(Conversation).filter_by(status="escalated").count()
    assert session.query(Escalation).count() == escalated_count


def test_seed_admin_demo_data_produces_events_usable_by_metrics():
    session = make_session()

    seed_admin_demo_data(session)

    assert session.query(Event).filter_by(type="retrieval").count() > 0
    assert session.query(Event).filter_by(type="tool_call").count() > 0
    assert session.query(Event).filter_by(type="intent").count() > 0


def test_seed_admin_demo_data_is_idempotent_on_rerun():
    session = make_session()

    seed_admin_demo_data(session)
    first_count = session.query(Conversation).count()

    seed_admin_demo_data(session)
    second_count = session.query(Conversation).count()

    assert first_count == second_count
