"""Escalation & handoff: builds the packet a human agent needs to take over.

attempted_actions always comes from the events table, never from the LLM's
memory of the conversation — see attempted_actions_from_events().
"""

import json

from app import intent as intent_module
from app.models import Conversation, Escalation, Event

_PACKET_PROMPT = """A customer support conversation is being escalated to a human agent.
Escalation reason: {reason}
Actions attempted so far: {attempted_actions}

Respond with ONLY a JSON object (no other text) with exactly these keys:
- "summary": one or two sentences a human agent can read to understand the situation
- "sentiment": one word describing the customer's tone (e.g. neutral, frustrated, angry)
- "suggested_action": a concrete next step for the human agent
"""

_FALLBACK_SUMMARY = "Escalated conversation — see the event log for full detail."
_FALLBACK_SENTIMENT = "neutral"
_FALLBACK_SUGGESTED_ACTION = "Review the conversation and attempted actions manually."


def build_handoff_packet(session, conversation_id: int, reason: str, llm_complete) -> dict:
    """One structured LLM call for summary/sentiment/suggested_action;
    attempted_actions is always derived from the events table, never taken
    from the LLM's response, even if it supplies one."""
    attempted_actions = attempted_actions_from_events(session, conversation_id)

    prompt = _PACKET_PROMPT.format(reason=reason, attempted_actions=attempted_actions)
    response = llm_complete([{"role": "user", "content": prompt}], tools=None)

    try:
        parsed = json.loads(response.content)
        if not isinstance(parsed, dict):
            parsed = {}
    except (TypeError, ValueError):
        parsed = {}

    return {
        "reason": reason,
        "summary": parsed.get("summary") or _FALLBACK_SUMMARY,
        "sentiment": parsed.get("sentiment") or _FALLBACK_SENTIMENT,
        "attempted_actions": attempted_actions,
        "suggested_action": parsed.get("suggested_action") or _FALLBACK_SUGGESTED_ACTION,
    }


def create_escalation(session, customer_id: int, conversation_id: int, reason: str, llm_complete) -> dict:
    """Build the handoff packet, open an Escalation row, flip the conversation
    to `escalated`, and log an `escalation` event. Returns a reference and an
    honest customer-facing message."""
    packet = build_handoff_packet(session, conversation_id, reason, llm_complete)

    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        conversation = Conversation(id=conversation_id, customer_id=customer_id, status="escalated")
        session.add(conversation)
    else:
        conversation.status = "escalated"

    row = Escalation(
        conversation_id=conversation_id,
        reason=packet["reason"],
        summary=packet["summary"],
        sentiment=packet["sentiment"],
        attempted_actions=packet["attempted_actions"],
        suggested_action=packet["suggested_action"],
        status="open",
    )
    session.add(row)
    session.commit()

    reference = f"E-{row.id}"
    session.add(
        Event(
            conversation_id=conversation_id,
            type="escalation",
            payload={"escalation_id": row.id, "reference": reference, **packet},
        )
    )
    session.commit()

    # F-005's intent breakdown needs one cheap classification per conversation
    # "at close/escalation" — escalation is the only close trigger that exists today.
    intent_module.classify_intent(session, conversation_id, llm_complete)

    message = (
        f"I've raised this with our support team with full context — reference #{reference}; "
        "expect a response within 4 business hours."
    )
    return {"escalation_id": row.id, "reference": reference, "message": message, "packet": packet}


def claim_escalation(session, escalation_id: int) -> Escalation | None:
    """Flip an open escalation to claimed. Idempotent — claiming an
    already-claimed row is a no-op, not an error."""
    row = session.get(Escalation, escalation_id)
    if row is None:
        return None
    row.status = "claimed"
    session.commit()
    return row


def attempted_actions_from_events(session, conversation_id: int) -> list[str]:
    """Chronological list of what the agent actually did in this conversation:
    executed tool calls by name, plus any non-ALLOW policy decision formatted
    as "tool → OUTCOME(reason)". ALLOW decisions are skipped — the matching
    tool_call event already represents them, so including both would duplicate
    the same action twice in the packet."""
    events = (
        session.query(Event)
        .filter(Event.conversation_id == conversation_id, Event.type.in_(["tool_call", "policy_decision"]))
        .order_by(Event.id)
        .all()
    )

    actions = []
    for event in events:
        if event.type == "tool_call":
            actions.append(event.payload["tool"])
        elif event.type == "policy_decision" and event.payload["outcome"] != "ALLOW":
            actions.append(f"{event.payload['tool']} → {event.payload['outcome']}({event.payload['reason']})")

    return actions
