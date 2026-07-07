from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import intent
from app.db import Base
from app.llm import LLMResponse
from app.models import Event, Message


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def fake_llm(content):
    def _complete(messages, tools=None):
        return LLMResponse(content=content, tool_calls=[])

    return _complete


def test_classify_intent_uses_llm_and_logs_an_intent_event():
    session = make_session()
    session.add(Message(conversation_id=1, role="user", content="Where is my order?"))
    session.commit()

    label = intent.classify_intent(session, conversation_id=1, llm_complete=fake_llm("order_status"))

    assert label == "order_status"
    events = session.query(Event).filter_by(type="intent", conversation_id=1).all()
    assert len(events) == 1
    assert events[0].payload["intent"] == "order_status"


def test_classify_intent_falls_back_to_other_for_unrecognized_label():
    session = make_session()
    session.add(Message(conversation_id=1, role="user", content="asdkjhaskjdh"))
    session.commit()

    label = intent.classify_intent(session, conversation_id=1, llm_complete=fake_llm("not-a-real-label"))

    assert label == "other"


def test_classify_intent_is_case_insensitive():
    session = make_session()
    session.add(Message(conversation_id=1, role="user", content="I want a refund"))
    session.commit()

    label = intent.classify_intent(session, conversation_id=1, llm_complete=fake_llm("  Refund  "))

    assert label == "refund"


def test_classify_intent_handles_conversations_with_no_messages():
    session = make_session()

    label = intent.classify_intent(session, conversation_id=1, llm_complete=fake_llm("other"))

    assert label == "other"
