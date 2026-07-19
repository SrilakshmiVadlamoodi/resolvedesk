from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import escalation
from app.db import Base
from app.llm import LLMResponse
from app.models import Conversation, Customer, Escalation, Event


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def fake_llm(content):
    def _complete(messages, tools=None, tool_choice=None):
        return LLMResponse(content=content, tool_calls=[])

    return _complete


PACKET_JSON = '{"summary": "s", "sentiment": "frustrated", "suggested_action": "approve manually"}'


def test_create_escalation_creates_open_escalation_row():
    session = make_session()
    customer = Customer(name="A", email="a@example.com", phone="1")
    session.add(customer)
    session.commit()

    result = escalation.create_escalation(
        session, customer_id=customer.id, conversation_id=1, reason="OVER_LIMIT", llm_complete=fake_llm(PACKET_JSON)
    )

    row = session.query(Escalation).one()
    assert row.status == "open"
    assert row.reason == "OVER_LIMIT"
    assert row.sentiment == "frustrated"
    assert result["reference"] == f"E-{row.id}"


def test_create_escalation_sets_conversation_status_to_escalated():
    session = make_session()
    customer = Customer(name="A", email="a@example.com", phone="1")
    session.add(customer)
    session.commit()

    escalation.create_escalation(
        session, customer_id=customer.id, conversation_id=42, reason="LOW_CONFIDENCE", llm_complete=fake_llm(PACKET_JSON)
    )

    conversation = session.get(Conversation, 42)
    assert conversation is not None
    assert conversation.status == "escalated"


def test_create_escalation_message_includes_reference_and_timeline():
    session = make_session()
    customer = Customer(name="A", email="a@example.com", phone="1")
    session.add(customer)
    session.commit()

    result = escalation.create_escalation(
        session, customer_id=customer.id, conversation_id=1, reason="HUMAN_REQUESTED", llm_complete=fake_llm(PACKET_JSON)
    )

    assert result["reference"] in result["message"]
    assert "4 business hours" in result["message"]


def test_create_escalation_logs_an_escalation_event():
    session = make_session()
    customer = Customer(name="A", email="a@example.com", phone="1")
    session.add(customer)
    session.commit()

    escalation.create_escalation(
        session, customer_id=customer.id, conversation_id=1, reason="OVER_LIMIT", llm_complete=fake_llm(PACKET_JSON)
    )

    events = session.query(Event).filter_by(type="escalation", conversation_id=1).all()
    assert len(events) == 1
    assert events[0].payload["reason"] == "OVER_LIMIT"
