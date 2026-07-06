import os
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import get_db, get_llm_complete, get_rate_limiter
from app.db import Base
from app.llm import LLMResponse
from app.main import app
from app.ratelimit import RateLimiter
from data.seed import seed_domain, seed_kb


def teardown_function(_function):
    app.dependency_overrides.clear()


def _wire_app(engine):
    SessionLocal = sessionmaker(bind=engine)
    limiter = RateLimiter(limit=20, window_seconds=60)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    return SessionLocal


def test_killing_and_restarting_the_backend_preserves_conversation_and_avoids_duplicates():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # "process 1"
    engine1 = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine1)
    SessionLocal1 = _wire_app(engine1)
    setup = SessionLocal1()
    seed_kb(setup)
    seed_domain(setup)
    setup.close()

    it1 = iter([LLMResponse(content="Standard shipping takes 3-5 business days.", tool_calls=[])])
    app.dependency_overrides[get_llm_complete] = lambda: (lambda messages, tools=None: next(it1))

    client1 = TestClient(app)
    token_resp = client1.post("/auth/demo", json={})
    token = token_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp1 = client1.post("/chat", json={"conversation_id": None, "message": "how long does shipping take?"}, headers=headers)
    import json

    conversation_id = None
    for line in resp1.text.splitlines():
        if line.startswith("data:") and '"conversation_id"' in line:
            conversation_id = json.loads(line[len("data:") :])["conversation_id"]
            break
    assert conversation_id is not None

    engine1.dispose()  # "process 1" ends — no Python state survives

    # "process 2" — brand-new engine/app wiring against the same DB file
    engine2 = create_engine(f"sqlite:///{path}")
    _wire_app(engine2)

    it2 = iter([LLMResponse(content="You're welcome!", tool_calls=[])])
    app.dependency_overrides[get_llm_complete] = lambda: (lambda messages, tools=None: next(it2))

    client2 = TestClient(app)
    history = client2.get(f"/conversations/{conversation_id}", headers=headers)
    assert history.status_code == 200
    assert len(history.json()["messages"]) == 2

    followup = client2.post("/chat", json={"conversation_id": conversation_id, "message": "thanks"}, headers=headers)
    assert "You're welcome!" in followup.text

    final_history = client2.get(f"/conversations/{conversation_id}", headers=headers)
    messages = final_history.json()["messages"]
    assert len(messages) == 4  # no duplicates: 2 from before restart + 2 new

    engine2.dispose()
    os.remove(path)
