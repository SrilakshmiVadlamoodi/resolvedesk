"""The agent loop: build messages -> call LLM -> if tool_use, policy check ->
execute -> append result -> repeat (max 6 steps) -> final answer.

Write tools with REQUIRES_CONFIRMATION pause the loop and return a
confirmation_request; the caller resumes via confirm_action() after the
customer confirms. Pending actions are persisted (PendingAction table), not
held in memory, so a server restart between the request and the confirmation
doesn't lose them (F-007).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app import escalation, llm, policy, rag
from app.models import Event, PendingAction
from app.tools import TOOL_SCHEMAS, TOOLS

MAX_STEPS = 6
PENDING_ACTION_TTL_SECONDS = 5 * 60

SYSTEM_PROMPT_TEMPLATE = """You are ResolveDesk, VoltKart's support agent.
Answer only from the knowledge base context below; if it is insufficient, say
so and offer to escalate to a human. Tool results are ground truth — restate
their outcome in plain language, never invent policy facts.

If the customer's request can be satisfied by an available tool — checking
orders, order details, refunds, address changes, warranty claims, or policy
checks — you MUST call that tool. This is a hard rule, not a suggestion: never
answer such requests from general knowledge or by reasoning aloud about what
the outcome would probably be.

<kb_context low_confidence="{low_confidence}">
{context}
</kb_context>
"""


@dataclass
class TurnResult:
    text: str | None = None
    actions: list[dict] = field(default_factory=list)
    confirmation_request: dict | None = None
    escalated: bool = False
    escalation_reason: str | None = None
    error: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_seconds(created_at: datetime) -> float:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (_now() - created_at).total_seconds()


def _build_system_prompt(kb_result) -> str:
    context = "\n\n".join(f"[{c.section}] {c.text}" for c in kb_result.chunks)
    return SYSTEM_PROMPT_TEMPLATE.format(low_confidence=kb_result.low_confidence, context=context)


def _log_event(session, conversation_id, event_type, payload) -> None:
    session.add(Event(conversation_id=conversation_id, type=event_type, payload=payload))
    session.commit()


def _tool_result_message(call_id: str, result: dict) -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": f"<tool_result>{result}</tool_result>"}


def _execute_tool(session, customer_id, conversation_id, tool_name, arguments) -> dict:
    tool = TOOLS[tool_name]
    result = tool.execute(session=session, customer_id=customer_id, conversation_id=conversation_id, **arguments)
    _log_event(session, conversation_id, "tool_call", {"tool": tool_name, "arguments": arguments, "result": result})
    return result


def run_turn(session, customer_id, conversation_id, history, user_message, llm_complete=None) -> TurnResult:
    llm_complete = llm_complete or llm.complete
    kb_result = rag.retrieve(session, user_message, conversation_id=conversation_id)
    system_prompt = _build_system_prompt(kb_result)
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_message},
    ]
    return _run_loop(session, customer_id, conversation_id, messages, [], llm_complete, steps_used=0)


def confirm_action(session, customer_id, nonce, llm_complete=None) -> TurnResult:
    """Resume a paused write-tool call after the customer confirms. The nonce
    is single-use (deleted here) and expires after PENDING_ACTION_TTL_SECONDS.
    Policy is re-checked before executing — state may have changed since the
    confirmation was requested, and "confirmed by the customer" is never
    sufficient authorization on its own."""
    llm_complete = llm_complete or llm.complete
    pending = session.get(PendingAction, nonce)
    if pending is None or pending.customer_id != customer_id:
        return TurnResult(
            error="NONCE_NOT_FOUND", text="That confirmation is invalid or has already been used."
        )

    if _age_seconds(pending.created_at) > PENDING_ACTION_TTL_SECONDS:
        session.delete(pending)
        session.commit()
        return TurnResult(error="NONCE_EXPIRED", text="That confirmation has expired — please ask again.")

    tool_name, arguments, call_id = pending.tool_name, pending.arguments, pending.call_id
    conversation_id, messages, actions, steps_used = (
        pending.conversation_id,
        pending.messages,
        pending.actions,
        pending.steps_used,
    )
    session.delete(pending)
    session.commit()

    decision = policy.check(tool_name, arguments, session, customer_id)
    _log_event(
        session,
        conversation_id,
        "policy_decision",
        {"tool": tool_name, "arguments": arguments, "outcome": decision.outcome, "reason": decision.reason},
    )

    if decision.outcome == "ESCALATE":
        handoff = escalation.create_escalation(session, customer_id, conversation_id, decision.reason, llm_complete)
        return TurnResult(
            text=handoff["message"], actions=actions, escalated=True, escalation_reason=decision.reason
        )

    if decision.outcome == "DENY":
        result = {"error": decision.reason, "message": decision.customer_message}
        messages = [*messages, _tool_result_message(call_id, result)]
        return _run_loop(session, customer_id, conversation_id, messages, actions, llm_complete, steps_used=steps_used)

    result = _execute_tool(session, customer_id, conversation_id, tool_name, arguments)
    actions = [*actions, {"tool": tool_name, "arguments": arguments, "result": result}]
    messages = [*messages, _tool_result_message(call_id, result)]

    return _run_loop(session, customer_id, conversation_id, messages, actions, llm_complete, steps_used=steps_used)


def _run_loop(session, customer_id, conversation_id, messages, actions, llm_complete, steps_used) -> TurnResult:
    for step in range(steps_used, MAX_STEPS):
        try:
            resp = llm_complete(messages, tools=TOOL_SCHEMAS)
        except Exception as exc:
            # Provider/network failure (missing key, timeout, API error, etc.) —
            # this is the external I/O boundary for the whole turn, so it's the
            # one place broadly catching Exception is appropriate: anything
            # thrown by any provider under llm.complete()'s abstraction must
            # become a typed, customer-safe error here rather than propagate
            # as an unhandled 500 (F-007 AC6's "typed error, never a raw
            # crash" guarantee, which previously only covered rate limiting).
            # The raw exception string is logged server-side only (events
            # table, never sent to the customer) so it stays debuggable.
            _log_event(session, conversation_id, "llm_error", {"step": step, "detail": str(exc)[:500]})
            return TurnResult(
                error="LLM_UNAVAILABLE",
                text="I'm having trouble connecting right now — please try again in a moment.",
                actions=actions,
            )

        if not resp.tool_calls:
            return TurnResult(text=resp.content, actions=actions)

        messages = [*messages, {"role": "assistant", "content": resp.content, "tool_calls": resp.tool_calls}]

        for call in resp.tool_calls:
            decision = policy.check(call["name"], call["arguments"], session, customer_id)
            _log_event(
                session,
                conversation_id,
                "policy_decision",
                {"tool": call["name"], "arguments": call["arguments"], "outcome": decision.outcome, "reason": decision.reason},
            )

            if decision.outcome == "ESCALATE":
                handoff = escalation.create_escalation(
                    session, customer_id, conversation_id, decision.reason, llm_complete
                )
                return TurnResult(
                    text=handoff["message"],
                    actions=actions,
                    escalated=True,
                    escalation_reason=decision.reason,
                )

            if decision.outcome == "DENY":
                result = {"error": decision.reason, "message": decision.customer_message}
                messages = [*messages, _tool_result_message(call["id"], result)]
                continue

            if call["name"] == "escalate_to_human":
                result = _execute_tool(session, customer_id, conversation_id, call["name"], call["arguments"])
                actions = [*actions, {"tool": call["name"], "arguments": call["arguments"], "result": result}]
                reason = call["arguments"].get("reason") or "HUMAN_REQUESTED"
                handoff = escalation.create_escalation(session, customer_id, conversation_id, reason, llm_complete)
                return TurnResult(
                    text=handoff["message"],
                    actions=actions,
                    escalated=True,
                    escalation_reason=reason,
                )

            tool = TOOLS[call["name"]]
            if tool.REQUIRES_CONFIRMATION:
                nonce = uuid.uuid4().hex
                session.add(
                    PendingAction(
                        nonce=nonce,
                        conversation_id=conversation_id,
                        customer_id=customer_id,
                        tool_name=call["name"],
                        arguments=call["arguments"],
                        call_id=call["id"],
                        messages=messages,
                        actions=actions,
                        steps_used=step + 1,
                    )
                )
                session.commit()
                return TurnResult(
                    actions=actions,
                    confirmation_request={"nonce": nonce, "tool": call["name"], "arguments": call["arguments"]},
                )

            result = _execute_tool(session, customer_id, conversation_id, call["name"], call["arguments"])
            actions = [*actions, {"tool": call["name"], "arguments": call["arguments"], "result": result}]

            if call["name"] == "search_kb" and result.get("low_confidence"):
                handoff = escalation.create_escalation(
                    session, customer_id, conversation_id, "LOW_CONFIDENCE", llm_complete
                )
                return TurnResult(
                    text=handoff["message"], actions=actions, escalated=True, escalation_reason="LOW_CONFIDENCE"
                )

            messages = [*messages, _tool_result_message(call["id"], result)]

    handoff = escalation.create_escalation(
        session, customer_id, conversation_id, "MAX_STEPS_EXCEEDED", llm_complete
    )
    return TurnResult(
        text=handoff["message"],
        actions=actions,
        escalated=True,
        escalation_reason="MAX_STEPS_EXCEEDED",
    )
