from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import get_db, get_llm_complete, get_rate_limiter
from app.db import Base
from app.llm import LLMResponse
from app.main import app
from app.models import Customer, Event, Refund
from app.ratelimit import RateLimiter
from data.seed import seed_domain, seed_kb


def make_client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    setup_session = SessionLocal()
    seed_kb(setup_session)
    seed_domain(setup_session)
    setup_session.close()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    default_limiter = RateLimiter(limit=20, window_seconds=60)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_rate_limiter] = lambda: default_limiter

    client = TestClient(app)
    return client, SessionLocal


def set_llm(*responses):
    it = iter(responses)

    def fake_llm(messages, tools=None):
        return next(it)

    app.dependency_overrides[get_llm_complete] = lambda: fake_llm


def auth_headers(client, customer_id=None):
    resp = client.post("/auth/demo", json={"customer_id": customer_id} if customer_id else {})
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def teardown_function(_function):
    app.dependency_overrides.clear()


def test_fresh_chat_creates_conversation_and_persists_both_messages():
    client, SessionLocal = make_client()
    set_llm(LLMResponse(content="Standard shipping takes 3-5 business days.", tool_calls=[]))
    headers = auth_headers(client)

    resp = client.post("/chat", json={"conversation_id": None, "message": "how long does shipping take?"}, headers=headers)

    assert resp.status_code == 200
    assert "event: conversation" in resp.text
    assert "event: token" in resp.text
    assert "event: done" in resp.text

    session = SessionLocal()
    from app.models import Message

    messages = session.query(Message).order_by(Message.id).all()
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "how long does shipping take?"
    assert "3-5 business days" in messages[1].content


def test_reload_then_continue_conversation_with_context_intact():
    client, SessionLocal = make_client()
    headers = auth_headers(client)

    set_llm(LLMResponse(content="Standard shipping takes 3-5 business days.", tool_calls=[]))
    first = client.post("/chat", json={"conversation_id": None, "message": "how long does shipping take?"}, headers=headers)
    conversation_id = None
    for line in first.text.splitlines():
        if line.startswith("data:") and "conversation_id" in line:
            import json

            conversation_id = json.loads(line[len("data:") :])["conversation_id"]
            break
    assert conversation_id is not None

    history_resp = client.get(f"/conversations/{conversation_id}", headers=headers)
    assert history_resp.status_code == 200
    assert len(history_resp.json()["messages"]) == 2

    set_llm(LLMResponse(content="You're welcome!", tool_calls=[]))
    followup = client.post("/chat", json={"conversation_id": conversation_id, "message": "thanks"}, headers=headers)
    assert followup.status_code == 200
    assert "You're welcome!" in followup.text

    final_history = client.get(f"/conversations/{conversation_id}", headers=headers)
    assert len(final_history.json()["messages"]) == 4


def test_refund_confirmation_flow_and_replayed_nonce_rejected():
    client, SessionLocal = make_client()
    headers = auth_headers(client)
    session = SessionLocal()
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    from app.models import Order

    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()
    order_id = order.id
    session.close()

    set_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "initiate_refund", "arguments": {"order_id": order_id, "amount": 2999, "reason": "x"}}],
        )
    )
    resp = client.post("/chat", json={"conversation_id": None, "message": "refund my order"}, headers=headers)
    assert "event: confirmation_request" in resp.text

    import json

    nonce = None
    conversation_id = None
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[len("data:") :])
            if "nonce" in data:
                nonce = data["nonce"]
            if "conversation_id" in data:
                conversation_id = data["conversation_id"]

    set_llm(LLMResponse(content="Your refund of ₹2999 will arrive in 5-7 business days.", tool_calls=[]))
    confirm = client.post("/chat/confirm", json={"conversation_id": conversation_id, "nonce": nonce}, headers=headers)
    assert confirm.status_code == 200
    assert "2999" in confirm.text

    session2 = SessionLocal()
    assert session2.query(Refund).count() == 1
    session2.close()

    set_llm()
    replay = client.post("/chat/confirm", json={"conversation_id": conversation_id, "nonce": nonce}, headers=headers)
    assert "event: error" in replay.text
    assert "NONCE_NOT_FOUND" in replay.text

    session3 = SessionLocal()
    assert session3.query(Refund).count() == 1  # not duplicated
    session3.close()


def test_requesting_another_customers_conversation_returns_404():
    client, SessionLocal = make_client()
    session = SessionLocal()
    rahul = session.query(Customer).filter_by(email="rahul@example.com").one()
    rahul_id = rahul.id
    session.close()

    aditi_headers = auth_headers(client)
    set_llm(LLMResponse(content="Hi there.", tool_calls=[]))
    chat_resp = client.post("/chat", json={"conversation_id": None, "message": "hello"}, headers=aditi_headers)

    import json

    conversation_id = None
    for line in chat_resp.text.splitlines():
        if line.startswith("data:") and '"conversation_id"' in line:
            conversation_id = json.loads(line[len("data:") :])["conversation_id"]
            break

    rahul_headers = auth_headers(client, customer_id=rahul_id)
    resp = client.get(f"/conversations/{conversation_id}", headers=rahul_headers)

    assert resp.status_code == 404


def test_exceeding_rate_limit_returns_typed_error_event():
    client, SessionLocal = make_client()
    limiter = RateLimiter(limit=1, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    headers = auth_headers(client)

    set_llm(LLMResponse(content="Hi.", tool_calls=[]), LLMResponse(content="Hi again.", tool_calls=[]))
    first = client.post("/chat", json={"conversation_id": None, "message": "hello"}, headers=headers)
    assert first.status_code == 200

    second = client.post("/chat", json={"conversation_id": None, "message": "hello again"}, headers=headers)
    assert "event: error" in second.text
    assert "RATE_LIMITED" in second.text


def test_llm_failure_returns_typed_error_event_not_a_500():
    client, _SessionLocal = make_client()
    headers = auth_headers(client)

    def raising_llm(messages, tools=None):
        raise RuntimeError("upstream unavailable")

    app.dependency_overrides[get_llm_complete] = lambda: raising_llm

    response = client.post("/chat", json={"conversation_id": None, "message": "where's my order?"}, headers=headers)

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "LLM_UNAVAILABLE" in response.text
    assert "upstream unavailable" not in response.text


def test_every_chat_call_produces_at_least_one_event_row():
    client, SessionLocal = make_client()
    headers = auth_headers(client)

    session = SessionLocal()
    before = session.query(Event).count()
    session.close()

    set_llm(LLMResponse(content="Hi.", tool_calls=[]))
    client.post("/chat", json={"conversation_id": None, "message": "hello"}, headers=headers)

    session2 = SessionLocal()
    after = session2.query(Event).count()
    session2.close()

    assert after > before
