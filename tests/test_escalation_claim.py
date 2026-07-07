from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import escalation
from app.db import Base
from app.models import Escalation


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_claim_escalation_flips_status_to_claimed():
    session = make_session()
    row = Escalation(conversation_id=1, reason="OVER_LIMIT", summary="s", sentiment="neutral", attempted_actions=[], suggested_action="a", status="open")
    session.add(row)
    session.commit()

    claimed = escalation.claim_escalation(session, row.id)

    assert claimed.status == "claimed"
    session.refresh(row)
    assert row.status == "claimed"


def test_claim_escalation_returns_none_for_unknown_id():
    session = make_session()

    result = escalation.claim_escalation(session, 999)

    assert result is None


def test_claiming_an_already_claimed_escalation_is_idempotent():
    session = make_session()
    row = Escalation(conversation_id=1, reason="OVER_LIMIT", summary="s", sentiment="neutral", attempted_actions=[], suggested_action="a", status="claimed")
    session.add(row)
    session.commit()

    claimed = escalation.claim_escalation(session, row.id)

    assert claimed.status == "claimed"
