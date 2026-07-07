from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import admin_metrics
from app.db import Base
from app.models import Event


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _event(session, conversation_id, event_type, payload):
    session.add(Event(conversation_id=conversation_id, type=event_type, payload=payload))
    session.commit()


def test_trace_returns_events_in_chronological_order():
    session = make_session()
    _event(session, 1, "retrieval", {"query": "refund my order"})
    _event(session, 1, "tool_call", {"tool": "get_order_details", "arguments": {}, "result": {}})
    _event(session, 1, "policy_decision", {"tool": "initiate_refund", "outcome": "ALLOW", "reason": "WITHIN_POLICY"})
    _event(session, 1, "tool_call", {"tool": "initiate_refund", "arguments": {}, "result": {"status": "approved"}})

    trace = admin_metrics.build_trace(session, conversation_id=1)

    assert [e["type"] for e in trace] == ["retrieval", "tool_call", "policy_decision", "tool_call"]
    assert trace[1]["payload"]["tool"] == "get_order_details"
    assert trace[3]["payload"]["tool"] == "initiate_refund"


def test_trace_is_scoped_to_the_requested_conversation():
    session = make_session()
    _event(session, 1, "retrieval", {"query": "a"})
    _event(session, 2, "retrieval", {"query": "b"})

    trace = admin_metrics.build_trace(session, conversation_id=1)

    assert len(trace) == 1
    assert trace[0]["payload"]["query"] == "a"


def test_trace_is_empty_for_unknown_conversation():
    session = make_session()

    trace = admin_metrics.build_trace(session, conversation_id=999)

    assert trace == []
