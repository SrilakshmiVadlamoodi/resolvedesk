from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import agent, escalation
from app.db import Base
from app.llm import LLMResponse
from app.models import Customer, Escalation, Order
from data.seed import seed_domain, seed_kb


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    return session


def fake_llm(*responses):
    it = iter(responses)

    def _complete(messages, tools=None):
        return next(it)

    return _complete


PACKET_JSON = '{"summary": "Customer asked for a human directly.", "sentiment": "neutral", "suggested_action": "Take over the conversation."}'


def test_explicit_human_request_escalates_immediately_without_agent_argument():
    session = make_session()
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()

    llm = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[
                {
                    "id": "1",
                    "name": "escalate_to_human",
                    "arguments": {"reason": "human_requested", "summary": "Customer explicitly asked for a human."},
                }
            ],
        ),
        LLMResponse(content=PACKET_JSON, tool_calls=[]),
        LLMResponse(content="other", tool_calls=[]),
    )

    result = agent.run_turn(session, aditi.id, conversation_id=1, history=[], user_message="talk to a human", llm_complete=llm)

    assert result.escalated is True
    assert "reference #E-" in result.text
    assert session.query(Escalation).count() == 1


def test_refund_over_ceiling_escalation_has_correct_reason_and_nonempty_suggested_action():
    session = make_session()
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    llm = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[
                {"id": "1", "name": "initiate_refund", "arguments": {"order_id": order.id, "amount": 8499, "reason": "too expensive to wait"}}
            ],
        ),
        LLMResponse(
            content='{"summary": "Customer wants ₹8,499 refund, over the auto-approve ceiling.", '
            '"sentiment": "frustrated", "suggested_action": "Approve manually — order qualifies on every rule except amount."}',
            tool_calls=[],
        ),
        LLMResponse(content="refund", tool_calls=[]),
    )

    result = agent.run_turn(session, aditi.id, conversation_id=1, history=[], user_message="refund my ₹8,499 order", llm_complete=llm)

    assert result.escalation_reason == "OVER_LIMIT"
    row = session.query(Escalation).one()
    assert row.reason == "OVER_LIMIT"
    assert row.suggested_action.startswith("Approve manually")


def test_handoff_packet_attempted_actions_exactly_matches_logged_events():
    session = make_session()
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    llm = fake_llm(
        LLMResponse(content=None, tool_calls=[{"id": "1", "name": "get_customer_orders", "arguments": {}}]),
        LLMResponse(
            content=None,
            tool_calls=[
                {"id": "2", "name": "initiate_refund", "arguments": {"order_id": order.id, "amount": 8499, "reason": "x"}}
            ],
        ),
        LLMResponse(content=PACKET_JSON, tool_calls=[]),
        LLMResponse(content="refund", tool_calls=[]),
    )

    result = agent.run_turn(session, aditi.id, conversation_id=9, history=[], user_message="check my order then refund it", llm_complete=llm)

    row = session.query(Escalation).filter_by(conversation_id=9).one()
    expected = escalation.attempted_actions_from_events(session, conversation_id=9)
    assert row.attempted_actions == expected
    assert result.escalated is True


def test_low_confidence_kb_search_escalates():
    session = make_session()
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()

    llm = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "search_kb", "arguments": {"query": "do you sell refrigerators"}}],
        ),
        LLMResponse(content=PACKET_JSON, tool_calls=[]),
        LLMResponse(content="other", tool_calls=[]),
    )

    result = agent.run_turn(session, aditi.id, conversation_id=1, history=[], user_message="do you sell refrigerators", llm_complete=llm)

    assert result.escalated is True
    assert result.escalation_reason == "LOW_CONFIDENCE"


def test_customer_can_ask_an_unrelated_question_after_escalation():
    session = make_session()
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()

    llm1 = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "escalate_to_human", "arguments": {"reason": "human_requested", "summary": "x"}}],
        ),
        LLMResponse(content=PACKET_JSON, tool_calls=[]),
        LLMResponse(content="other", tool_calls=[]),
    )
    escalated = agent.run_turn(session, aditi.id, conversation_id=1, history=[], user_message="talk to a human", llm_complete=llm1)
    assert escalated.escalated is True

    llm2 = fake_llm(LLMResponse(content="Standard shipping takes 3-5 business days.", tool_calls=[]))
    followup = agent.run_turn(session, aditi.id, conversation_id=1, history=[], user_message="how long does shipping take?", llm_complete=llm2)

    assert followup.escalated is False
    assert followup.text == "Standard shipping takes 3-5 business days."
