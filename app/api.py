"""HTTP surface for the agent loop: demo auth, chat (SSE), confirmation, and
conversation history. Wraps F-002's run_turn/confirm_action; owns the wire
protocol and persistence, not the reasoning."""

import json

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import agent, auth, llm
from app.db import get_session
from app.models import Conversation, Customer, Event, Message
from app.ratelimit import chat_rate_limiter

router = APIRouter()

_ACTION_TYPE_MAP = {
    "initiate_refund": "refund_initiated",
    "update_shipping_address": "address_updated",
    "file_warranty_claim": "warranty_claim_filed",
}


class AuthDemoRequest(BaseModel):
    customer_id: int | None = None


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str


class ChatConfirmRequest(BaseModel):
    conversation_id: int
    nonce: str


def get_db():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def get_llm_complete():
    return llm.complete


def get_rate_limiter():
    return chat_rate_limiter


def _bearer_token(authorization: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:]
    return ""


def resolve_customer_id(authorization: str | None = Header(default=None)) -> int:
    customer_id = auth.resolve_token(_bearer_token(authorization))
    if customer_id is None:
        raise HTTPException(status_code=401, detail="invalid or missing session token")
    return customer_id


def _get_owned_conversation(db: Session, conversation_id: int, customer_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.customer_id != customer_id:
        # 404, not 403 — don't reveal that the id exists for another customer.
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _turn_result_to_sse(result: agent.TurnResult, conversation_id: int) -> list[str]:
    events: list[str] = []

    for action in result.actions:
        action_type = _ACTION_TYPE_MAP.get(action["tool"])
        if action_type and "error" not in action["result"]:
            events.append(_sse("action", {"type": action_type, **action["arguments"], **action["result"]}))

    if result.confirmation_request:
        events.append(_sse("confirmation_request", {"conversation_id": conversation_id, **result.confirmation_request}))
    elif result.error:
        events.append(_sse("error", {"code": result.error, "message": result.text}))
    elif result.escalated:
        events.append(
            _sse("escalated", {"conversation_id": conversation_id, "reason": result.escalation_reason, "message": result.text})
        )
    else:
        events.append(_sse("token", {"text": result.text}))

    events.append(_sse("done", {"conversation_id": conversation_id}))
    return events


@router.post("/auth/demo")
def auth_demo(body: AuthDemoRequest, db: Session = Depends(get_db)):
    customer_id = body.customer_id
    if customer_id is None:
        default_customer = db.query(Customer).order_by(Customer.id).first()
        if default_customer is None:
            raise HTTPException(status_code=400, detail="no demo customers seeded")
        customer_id = default_customer.id
    return {"token": auth.create_demo_token(customer_id), "customer_id": customer_id}


@router.post("/chat")
def chat(
    body: ChatRequest,
    authorization: str | None = Header(default=None),
    customer_id: int = Depends(resolve_customer_id),
    db: Session = Depends(get_db),
    llm_complete=Depends(get_llm_complete),
    limiter=Depends(get_rate_limiter),
):
    token = _bearer_token(authorization)
    if not limiter.allow(token):
        db.add(Event(conversation_id=body.conversation_id, type="rate_limited", payload={"token": token}))
        db.commit()
        events = [_sse("error", {"code": "RATE_LIMITED", "message": "Too many messages — please slow down and try again shortly."})]
        return StreamingResponse(iter(events), media_type="text/event-stream")

    lead_events: list[str] = []
    if body.conversation_id is None:
        conversation = Conversation(customer_id=customer_id, status="active")
        db.add(conversation)
        db.commit()
        conversation_id = conversation.id
        lead_events.append(_sse("conversation", {"conversation_id": conversation_id}))
    else:
        conversation = _get_owned_conversation(db, body.conversation_id, customer_id)
        conversation_id = conversation.id

    history = [
        {"role": m.role, "content": m.content}
        for m in db.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.id).all()
    ]

    db.add(Message(conversation_id=conversation_id, role="user", content=body.message))
    db.commit()

    result = agent.run_turn(db, customer_id, conversation_id, history, body.message, llm_complete=llm_complete)

    if result.text and not result.error:
        db.add(Message(conversation_id=conversation_id, role="assistant", content=result.text))
        db.commit()

    events = lead_events + _turn_result_to_sse(result, conversation_id)
    return StreamingResponse(iter(events), media_type="text/event-stream")


@router.post("/chat/confirm")
def chat_confirm(
    body: ChatConfirmRequest,
    customer_id: int = Depends(resolve_customer_id),
    db: Session = Depends(get_db),
    llm_complete=Depends(get_llm_complete),
):
    _get_owned_conversation(db, body.conversation_id, customer_id)

    result = agent.confirm_action(db, customer_id, body.nonce, llm_complete=llm_complete)

    if result.text and not result.error:
        db.add(Message(conversation_id=body.conversation_id, role="assistant", content=result.text))
        db.commit()

    events = _turn_result_to_sse(result, body.conversation_id)
    return StreamingResponse(iter(events), media_type="text/event-stream")


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int, customer_id: int = Depends(resolve_customer_id), db: Session = Depends(get_db)
):
    conversation = _get_owned_conversation(db, conversation_id, customer_id)
    messages = db.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.id).all()
    return {
        "conversation_id": conversation_id,
        "status": conversation.status,
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages
        ],
    }
