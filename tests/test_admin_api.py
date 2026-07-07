from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import get_db
from app.db import Base
from app.main import app
from app.models import Conversation, Escalation, Event


def make_client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

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


def test_metrics_requires_the_demo_key():
    client, _ = make_client()

    resp = client.get("/admin/metrics")

    assert resp.status_code == 401


def test_metrics_returns_data_with_correct_key():
    client, SessionLocal = make_client()
    session = SessionLocal()
    session.add(Conversation(customer_id=1, status="resolved"))
    session.commit()
    session.close()

    resp = client.get("/admin/metrics?key=demo")

    assert resp.status_code == 200
    assert resp.json()["total_conversations"] == 1


def test_escalations_list_and_claim():
    client, SessionLocal = make_client()
    session = SessionLocal()
    row = Escalation(
        conversation_id=1, reason="OVER_LIMIT", summary="s", sentiment="neutral",
        attempted_actions=[], suggested_action="a", status="open",
    )
    session.add(row)
    session.commit()
    escalation_id = row.id
    session.close()

    listed = client.get("/admin/escalations?key=demo")
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "open"

    claimed = client.post(f"/admin/escalations/{escalation_id}/claim?key=demo")
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "claimed"

    listed_again = client.get("/admin/escalations?key=demo")
    assert listed_again.json()[0]["status"] == "claimed"


def test_claim_unknown_escalation_returns_404():
    client, _ = make_client()

    resp = client.post("/admin/escalations/999/claim?key=demo")

    assert resp.status_code == 404


def test_trace_returns_ordered_events_for_known_conversation():
    client, SessionLocal = make_client()
    session = SessionLocal()
    session.add(Conversation(id=1, customer_id=1, status="resolved"))
    session.add(Event(conversation_id=1, type="retrieval", payload={"query": "x"}))
    session.add(Event(conversation_id=1, type="tool_call", payload={"tool": "get_order_details", "arguments": {}, "result": {}}))
    session.commit()
    session.close()

    resp = client.get("/admin/conversations/1/trace?key=demo")

    assert resp.status_code == 200
    events = resp.json()["events"]
    assert [e["type"] for e in events] == ["retrieval", "tool_call"]


def test_trace_for_unknown_conversation_returns_404():
    client, _ = make_client()

    resp = client.get("/admin/conversations/999/trace?key=demo")

    assert resp.status_code == 404
