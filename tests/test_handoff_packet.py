from app import escalation
from app.llm import LLMResponse
from app.models import Event
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def fake_llm(content):
    def _complete(messages, tools=None, tool_choice=None):
        return LLMResponse(content=content, tool_calls=[])

    return _complete


def test_build_handoff_packet_uses_llm_for_summary_sentiment_and_suggested_action():
    session = make_session()
    session.add(
        Event(
            conversation_id=1,
            type="policy_decision",
            payload={"tool": "initiate_refund", "arguments": {"amount": 8499}, "outcome": "ESCALATE", "reason": "OVER_LIMIT"},
        )
    )
    session.commit()

    llm = fake_llm(
        '{"summary": "Customer wants ₹8,499 refund, over the auto-approve ceiling.", '
        '"sentiment": "frustrated", '
        '"suggested_action": "Approve manually — order qualifies on every rule except amount."}'
    )

    packet = escalation.build_handoff_packet(session, conversation_id=1, reason="OVER_LIMIT", llm_complete=llm)

    assert packet["reason"] == "OVER_LIMIT"
    assert packet["sentiment"] == "frustrated"
    assert "₹8,499" in packet["summary"]
    assert packet["suggested_action"].startswith("Approve manually")
    assert packet["attempted_actions"] == ["initiate_refund → ESCALATE(OVER_LIMIT)"]


def test_build_handoff_packet_attempted_actions_always_from_events_not_llm():
    session = make_session()
    session.add(Event(conversation_id=1, type="tool_call", payload={"tool": "get_order_details", "arguments": {}, "result": {}}))
    session.commit()

    llm = fake_llm('{"summary": "x", "sentiment": "neutral", "suggested_action": "y", "attempted_actions": ["made_up_tool"]}')

    packet = escalation.build_handoff_packet(session, conversation_id=1, reason="LOW_CONFIDENCE", llm_complete=llm)

    assert packet["attempted_actions"] == ["get_order_details"]


def test_build_handoff_packet_falls_back_gracefully_on_unparseable_llm_output():
    session = make_session()

    llm = fake_llm("not valid json")

    packet = escalation.build_handoff_packet(session, conversation_id=1, reason="HUMAN_REQUESTED", llm_complete=llm)

    assert packet["reason"] == "HUMAN_REQUESTED"
    assert packet["sentiment"]
    assert packet["summary"]
    assert packet["suggested_action"]
