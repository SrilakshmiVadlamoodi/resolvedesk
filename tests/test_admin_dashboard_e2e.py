"""End-to-end proof of F-005's acceptance criteria 1 and 3: a real refund
flow through the chat API visibly moves the admin metrics, and the trace
view shows the exact expected event order."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import get_db, get_llm_complete
from app.db import Base
from app.llm import LLMResponse
from app.main import app
from app.models import Customer, Order
from data.seed import seed_domain, seed_kb


def make_client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    setup = SessionLocal()
    seed_kb(setup)
    seed_domain(setup)
    setup.close()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def teardown_function(_function):
    app.dependency_overrides.clear()


def set_llm(*responses):
    it = iter(responses)

    def fake_llm(messages, tools=None):
        return next(it)

    app.dependency_overrides[get_llm_complete] = lambda: fake_llm


def test_refund_via_chat_updates_actions_taken_metric():
    client, SessionLocal = make_client()
    session = SessionLocal()
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()
    order_id = order.id
    session.close()

    token = client.post("/auth/demo", json={"customer_id": aditi.id}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    before = client.get("/admin/metrics?key=demo").json()
    assert before["refunds_initiated"] == 0

    set_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "initiate_refund", "arguments": {"order_id": order_id, "amount": 2999, "reason": "x"}}],
        )
    )
    chat_resp = client.post("/chat", json={"conversation_id": None, "message": "refund my order"}, headers=headers)
    import json

    nonce = conversation_id = None
    for line in chat_resp.text.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[len("data:") :])
            nonce = data.get("nonce", nonce)
            conversation_id = data.get("conversation_id", conversation_id)

    set_llm(LLMResponse(content="Your refund is on its way.", tool_calls=[]))
    client.post("/chat/confirm", json={"conversation_id": conversation_id, "nonce": nonce}, headers=headers)

    after = client.get("/admin/metrics?key=demo").json()
    assert after["refunds_initiated"] == 1
    assert after["total_refund_value"] == 2999


def test_trace_view_shows_expected_order_for_a_refund_conversation():
    client, SessionLocal = make_client()
    session = SessionLocal()
    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()
    order_id = order.id
    session.close()

    token = client.post("/auth/demo", json={"customer_id": aditi.id}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    set_llm(
        LLMResponse(content=None, tool_calls=[{"id": "1", "name": "get_order_details", "arguments": {"order_id": order_id}}]),
        LLMResponse(
            content=None,
            tool_calls=[{"id": "2", "name": "initiate_refund", "arguments": {"order_id": order_id, "amount": 2999, "reason": "x"}}],
        ),
    )
    chat_resp = client.post("/chat", json={"conversation_id": None, "message": "check my order then refund it"}, headers=headers)

    import json

    nonce = conversation_id = None
    for line in chat_resp.text.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[len("data:") :])
            nonce = data.get("nonce", nonce)
            conversation_id = data.get("conversation_id", conversation_id)

    set_llm(LLMResponse(content="Your refund is on its way.", tool_calls=[]))
    client.post("/chat/confirm", json={"conversation_id": conversation_id, "nonce": nonce}, headers=headers)

    trace_resp = client.get(f"/admin/conversations/{conversation_id}/trace?key=demo")
    events = trace_resp.json()["events"]

    def find(event_type, tool=None):
        for i, e in enumerate(events):
            if e["type"] == event_type and (tool is None or e["payload"].get("tool") == tool):
                return i
        return None

    i_retrieval = find("retrieval")
    i_get_order = find("tool_call", "get_order_details")
    i_policy_allow = find("policy_decision", "initiate_refund")
    i_refund = find("tool_call", "initiate_refund")

    assert None not in (i_retrieval, i_get_order, i_policy_allow, i_refund)
    assert events[i_policy_allow]["payload"]["outcome"] == "ALLOW"
    assert i_retrieval < i_get_order < i_policy_allow < i_refund
