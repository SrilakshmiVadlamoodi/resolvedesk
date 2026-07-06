from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import escalation
from app.db import Base
from app.models import Event


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _add_event(session, conversation_id, event_type, payload):
    session.add(Event(conversation_id=conversation_id, type=event_type, payload=payload))
    session.commit()


def test_attempted_actions_lists_executed_tool_calls_by_name():
    session = make_session()
    _add_event(session, 1, "tool_call", {"tool": "get_order_details", "arguments": {"order_id": 5}, "result": {}})

    actions = escalation.attempted_actions_from_events(session, conversation_id=1)

    assert actions == ["get_order_details"]


def test_attempted_actions_includes_non_allow_policy_decisions():
    session = make_session()
    _add_event(
        session,
        1,
        "policy_decision",
        {"tool": "initiate_refund", "arguments": {}, "outcome": "ESCALATE", "reason": "OVER_LIMIT"},
    )

    actions = escalation.attempted_actions_from_events(session, conversation_id=1)

    assert actions == ["initiate_refund → ESCALATE(OVER_LIMIT)"]


def test_attempted_actions_excludes_allow_policy_decisions_to_avoid_duplicates():
    session = make_session()
    _add_event(session, 1, "tool_call", {"tool": "get_customer_orders", "arguments": {}, "result": {}})
    _add_event(
        session,
        1,
        "policy_decision",
        {"tool": "get_customer_orders", "arguments": {}, "outcome": "ALLOW", "reason": "DEFAULT_ALLOW"},
    )

    actions = escalation.attempted_actions_from_events(session, conversation_id=1)

    assert actions == ["get_customer_orders"]


def test_attempted_actions_preserves_chronological_order_and_scopes_to_conversation():
    session = make_session()
    _add_event(session, 1, "tool_call", {"tool": "get_customer_orders", "arguments": {}, "result": {}})
    _add_event(session, 2, "tool_call", {"tool": "search_kb", "arguments": {}, "result": {}})
    _add_event(
        session,
        1,
        "policy_decision",
        {"tool": "initiate_refund", "arguments": {}, "outcome": "ESCALATE", "reason": "OVER_LIMIT"},
    )

    actions = escalation.attempted_actions_from_events(session, conversation_id=1)

    assert actions == ["get_customer_orders", "initiate_refund → ESCALATE(OVER_LIMIT)"]
