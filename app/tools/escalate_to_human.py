"""Control tool: hand off to a human agent. Handoff packet generation is F-004's job."""

NAME = "escalate_to_human"
REQUIRES_CONFIRMATION = False

SCHEMA = {
    "name": NAME,
    "description": "Escalate the conversation to a human agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["reason", "summary"],
    },
}


def execute(session, customer_id: int, reason: str, summary: str, **_kwargs) -> dict:
    return {"status": "escalated", "reason": reason, "summary": summary}
