"""Admin dashboard read model — entirely derived from events/conversations/
escalations, per F-005's spec: no separate counters that can drift out of
sync with what actually happened."""

from collections import Counter

from app.models import Conversation, Escalation, Event


def build_metrics(session) -> dict:
    conversations = session.query(Conversation).all()
    total = len(conversations)
    resolved = sum(1 for c in conversations if c.status == "resolved")
    escalated = sum(1 for c in conversations if c.status == "escalated")
    closed_ids = {c.id for c in conversations if c.status in ("resolved", "escalated")}

    tool_call_events = session.query(Event).filter_by(type="tool_call").all()
    retrieval_events = session.query(Event).filter_by(type="retrieval").all()
    escalations = session.query(Escalation).all()

    refunds_initiated = 0
    total_refund_value = 0.0
    addresses_updated = 0
    for event in tool_call_events:
        tool, result = event.payload["tool"], event.payload["result"]
        if "error" in result:
            continue
        if tool == "initiate_refund":
            refunds_initiated += 1
            total_refund_value += result["amount"]
        elif tool == "update_shipping_address":
            addresses_updated += 1

    retrieval_counts_per_conversation = Counter(
        e.conversation_id for e in retrieval_events if e.conversation_id in closed_ids
    )

    return {
        "total_conversations": total,
        "resolution_rate": (resolved / total) if total else 0.0,
        "escalation_rate": (escalated / total) if total else 0.0,
        "escalation_reasons": dict(Counter(e.reason for e in escalations)),
        "refunds_initiated": refunds_initiated,
        "total_refund_value": total_refund_value,
        "addresses_updated": addresses_updated,
        "avg_tool_calls_per_conversation": (len(tool_call_events) / total) if total else 0.0,
        "avg_turns_to_resolution": (
            sum(retrieval_counts_per_conversation.values()) / len(retrieval_counts_per_conversation)
            if retrieval_counts_per_conversation
            else 0.0
        ),
    }


def build_trace(session, conversation_id: int) -> list[dict]:
    """Chronological event timeline for one conversation — the 'glass box'
    view: retrievals, tool calls, policy decisions, escalations, in order."""
    events = (
        session.query(Event).filter_by(conversation_id=conversation_id).order_by(Event.id).all()
    )
    return [{"type": e.type, "payload": e.payload, "created_at": e.created_at.isoformat()} for e in events]
