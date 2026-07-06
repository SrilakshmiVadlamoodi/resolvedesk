import os
import tempfile
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import agent
from app.db import Base
from app.llm import LLMResponse
from app.models import Customer, PendingAction, Refund
from data.seed import seed_domain, seed_kb


def make_file_engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return engine, path


def fake_llm(*responses):
    it = iter(responses)

    def _complete(messages, tools=None):
        return next(it)

    return _complete


def test_confirmation_survives_a_simulated_process_restart():
    engine, path = make_file_engine()
    session1 = sessionmaker(bind=engine)()
    seed_kb(session1)
    seed_domain(session1)
    aditi = session1.query(Customer).filter_by(email="aditi@example.com").one()
    from app.models import Order

    order = session1.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()
    customer_id, order_id = aditi.id, order.id

    llm1 = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "initiate_refund", "arguments": {"order_id": order_id, "amount": 2999, "reason": "x"}}],
        )
    )
    result = agent.run_turn(session1, customer_id, conversation_id=1, history=[], user_message="refund it", llm_complete=llm1)
    nonce = result.confirmation_request["nonce"]
    session1.close()
    engine.dispose()  # simulate the process ending; only the DB file survives

    # "restart": brand-new engine/session pointed at the same file, no shared Python state
    engine2 = create_engine(f"sqlite:///{path}")
    session2 = sessionmaker(bind=engine2)()

    llm2 = fake_llm(LLMResponse(content="Your refund of ₹2999 will arrive in 5-7 business days.", tool_calls=[]))
    confirmed = agent.confirm_action(session2, customer_id, nonce, llm_complete=llm2)

    assert session2.query(Refund).count() == 1
    assert "2999" in confirmed.text

    session2.close()
    engine2.dispose()
    os.remove(path)


def test_nonce_is_single_use():
    engine, path = make_file_engine()
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    from app.models import Order

    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    llm1 = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "initiate_refund", "arguments": {"order_id": order.id, "amount": 2999, "reason": "x"}}],
        )
    )
    result = agent.run_turn(session, aditi.id, conversation_id=1, history=[], user_message="refund it", llm_complete=llm1)
    nonce = result.confirmation_request["nonce"]

    llm2 = fake_llm(LLMResponse(content="Done.", tool_calls=[]))
    first = agent.confirm_action(session, aditi.id, nonce, llm_complete=llm2)
    assert first.error is None

    second = agent.confirm_action(session, aditi.id, nonce, llm_complete=fake_llm())
    assert second.error == "NONCE_NOT_FOUND"
    assert session.query(Refund).count() == 1  # not double-refunded

    session.close()
    engine.dispose()
    os.remove(path)


def test_expired_nonce_is_rejected():
    engine, path = make_file_engine()
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    from app.models import Order

    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    session.add(
        PendingAction(
            nonce="stale-nonce",
            conversation_id=1,
            customer_id=aditi.id,
            tool_name="initiate_refund",
            arguments={"order_id": order.id, "amount": 2999, "reason": "x"},
            call_id="1",
            messages=[],
            actions=[],
            steps_used=1,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=6),
        )
    )
    session.commit()

    result = agent.confirm_action(session, aditi.id, "stale-nonce", llm_complete=fake_llm())

    assert result.error == "NONCE_EXPIRED"
    assert session.query(Refund).count() == 0

    session.close()
    engine.dispose()
    os.remove(path)
