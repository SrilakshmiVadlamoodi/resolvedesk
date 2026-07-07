from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import admin_metrics
from app.db import Base
from app.models import Conversation, Escalation, Event


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _conv(session, status):
    c = Conversation(customer_id=1, status=status)
    session.add(c)
    session.commit()
    return c


def _event(session, conversation_id, event_type, payload):
    session.add(Event(conversation_id=conversation_id, type=event_type, payload=payload))
    session.commit()


def test_resolution_and_escalation_rates():
    session = make_session()
    _conv(session, "resolved")
    _conv(session, "resolved")
    _conv(session, "escalated")
    _conv(session, "active")

    metrics = admin_metrics.build_metrics(session)

    assert metrics["total_conversations"] == 4
    assert metrics["resolution_rate"] == 0.5
    assert metrics["escalation_rate"] == 0.25


def test_escalation_breakdown_by_reason_comes_from_escalations_table():
    session = make_session()
    c1 = _conv(session, "escalated")
    c2 = _conv(session, "escalated")
    session.add(Escalation(conversation_id=c1.id, reason="OVER_LIMIT", summary="s", sentiment="neutral", attempted_actions=[], suggested_action="a"))
    session.add(Escalation(conversation_id=c2.id, reason="OVER_LIMIT", summary="s", sentiment="neutral", attempted_actions=[], suggested_action="a"))
    session.commit()

    metrics = admin_metrics.build_metrics(session)

    assert metrics["escalation_reasons"] == {"OVER_LIMIT": 2}


def test_actions_taken_and_refund_value_derived_from_tool_call_events():
    session = make_session()
    c = _conv(session, "resolved")
    _event(session, c.id, "tool_call", {"tool": "initiate_refund", "arguments": {"order_id": 1, "amount": 2999}, "result": {"refund_id": 1, "amount": 2999, "status": "approved"}})
    _event(session, c.id, "tool_call", {"tool": "initiate_refund", "arguments": {"order_id": 2, "amount": 1000}, "result": {"error": "not_found"}})
    _event(session, c.id, "tool_call", {"tool": "update_shipping_address", "arguments": {}, "result": {"order_id": 1, "new_address": "x", "status": "updated"}})

    metrics = admin_metrics.build_metrics(session)

    assert metrics["refunds_initiated"] == 1
    assert metrics["total_refund_value"] == 2999
    assert metrics["addresses_updated"] == 1


def test_avg_tool_calls_per_conversation():
    session = make_session()
    c1 = _conv(session, "resolved")
    _conv(session, "resolved")
    _event(session, c1.id, "tool_call", {"tool": "get_customer_orders", "arguments": {}, "result": {}})
    _event(session, c1.id, "tool_call", {"tool": "get_order_details", "arguments": {}, "result": {}})

    metrics = admin_metrics.build_metrics(session)

    assert metrics["avg_tool_calls_per_conversation"] == 1.0


def test_avg_turns_to_resolution_uses_retrieval_event_count_per_closed_conversation():
    session = make_session()
    c1 = _conv(session, "resolved")
    c2 = _conv(session, "escalated")
    c3 = _conv(session, "active")  # not closed, excluded
    for _ in range(2):
        _event(session, c1.id, "retrieval", {"query": "q", "chunk_ids": [], "scores": []})
    for _ in range(4):
        _event(session, c2.id, "retrieval", {"query": "q", "chunk_ids": [], "scores": []})
    _event(session, c3.id, "retrieval", {"query": "q", "chunk_ids": [], "scores": []})

    metrics = admin_metrics.build_metrics(session)

    assert metrics["avg_turns_to_resolution"] == 3.0


def test_metrics_are_empty_safe_with_no_conversations():
    session = make_session()

    metrics = admin_metrics.build_metrics(session)

    assert metrics["total_conversations"] == 0
    assert metrics["resolution_rate"] == 0.0
    assert metrics["escalation_rate"] == 0.0
    assert metrics["avg_tool_calls_per_conversation"] == 0.0
    assert metrics["avg_turns_to_resolution"] == 0.0
