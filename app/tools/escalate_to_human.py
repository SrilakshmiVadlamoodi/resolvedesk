"""Control tool: hand off to a human agent. Handoff packet generation is F-004's job."""

NAME = "escalate_to_human"
REQUIRES_CONFIRMATION = False

REASON_CODES = [
    "HUMAN_REQUESTED",
    "OVER_LIMIT",
    "WINDOW_EXPIRED",
    "DUPLICATE",
    "LOW_CONFIDENCE",
    "MAX_STEPS_EXCEEDED",
]

SCHEMA = {
    "name": NAME,
    "description": "Escalate the conversation to a human agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "enum": REASON_CODES,
                "description": (
                    "MUST be exactly one of: " + ", ".join(REASON_CODES) + ". "
                    "No other values are valid — do not paraphrase, describe, or invent a "
                    "new reason string. Pick the single closest code from this list."
                ),
            },
            "summary": {
                "type": "string",
                "description": "A free-text summary of the conversation for the human agent. "
                "This is the only field that may contain free text.",
            },
        },
        "required": ["reason", "summary"],
    },
}


def execute(session, customer_id: int, reason: str, summary: str, **_kwargs) -> dict:
    return {"status": "escalated", "reason": reason, "summary": summary}
