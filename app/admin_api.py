"""Admin dashboard API: a read model over events/conversations/escalations,
plus the one write action (Claim). No real auth — a static demo key in the
query string (?key=demo), a deliberate scope cut per spec."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import admin_metrics, escalation
from app.api import get_db
from app.models import Conversation, Escalation

router = APIRouter(prefix="/admin")

DEMO_KEY = "demo"


def require_demo_key(key: str = Query(default="")) -> None:
    if key != DEMO_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing admin key")


@router.get("/metrics", dependencies=[Depends(require_demo_key)])
def get_metrics(db: Session = Depends(get_db)):
    return admin_metrics.build_metrics(db)


@router.get("/escalations", dependencies=[Depends(require_demo_key)])
def list_escalations(db: Session = Depends(get_db)):
    rows = db.query(Escalation).order_by(Escalation.id.desc()).all()
    return [
        {
            "id": r.id,
            "conversation_id": r.conversation_id,
            "reason": r.reason,
            "summary": r.summary,
            "sentiment": r.sentiment,
            "attempted_actions": r.attempted_actions,
            "suggested_action": r.suggested_action,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/escalations/{escalation_id}/claim", dependencies=[Depends(require_demo_key)])
def claim(escalation_id: int, db: Session = Depends(get_db)):
    row = escalation.claim_escalation(db, escalation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="escalation not found")
    return {"id": row.id, "status": row.status}


@router.get("/conversations/{conversation_id}/trace", dependencies=[Depends(require_demo_key)])
def trace(conversation_id: int, db: Session = Depends(get_db)):
    if db.get(Conversation, conversation_id) is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"conversation_id": conversation_id, "events": admin_metrics.build_trace(db, conversation_id)}
