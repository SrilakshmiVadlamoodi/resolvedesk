"""Read tool: search the VoltKart knowledge base (wraps F-001's retrieve())."""

from app.rag import retrieve

NAME = "search_kb"
REQUIRES_CONFIRMATION = False

SCHEMA = {
    "name": NAME,
    "description": "Search the VoltKart knowledge base for policy/product information.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}


def execute(session, customer_id: int, query: str, conversation_id: int | None = None, **_kwargs) -> dict:
    result = retrieve(session, query, conversation_id=conversation_id)
    return {
        "chunks": [
            {"section": c.section, "text": c.text, "score": c.score} for c in result.chunks
        ],
        "low_confidence": result.low_confidence,
    }
