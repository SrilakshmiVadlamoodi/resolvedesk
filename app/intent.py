"""One cheap LLM classification per conversation at close/escalation, so the
admin dashboard's intent breakdown is a real signal instead of a guess."""

from app.models import Event, Message

INTENT_LABELS = ["order_status", "refund", "warranty", "product_question", "other"]


def classify_intent(session, conversation_id: int, llm_complete) -> str:
    messages = (
        session.query(Message)
        .filter_by(conversation_id=conversation_id, role="user")
        .order_by(Message.id)
        .all()
    )
    transcript = "\n".join(m.content for m in messages) or "(no message text available)"

    prompt = (
        "Classify the customer's primary intent in this conversation into exactly one of: "
        f"{', '.join(INTENT_LABELS)}.\n\nConversation:\n{transcript}\n\n"
        "Respond with only the label, nothing else."
    )
    response = llm_complete([{"role": "user", "content": prompt}], tools=None)

    label = (response.content or "").strip().lower()
    if label not in INTENT_LABELS:
        label = "other"

    session.add(Event(conversation_id=conversation_id, type="intent", payload={"intent": label}))
    session.commit()

    return label
