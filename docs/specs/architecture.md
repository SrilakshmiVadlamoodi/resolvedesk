# Architecture — ResolveDesk

## System overview

```
┌───────────────────────────────────────────────────────────────┐
│                        Frontend (Vercel)                      │
│  ┌──────────────────┐          ┌───────────────────────────┐  │
│  │  Customer Chat   │          │  Admin Dashboard          │  │
│  │  (React, SSE)    │          │  (metrics, traces, queue) │  │
│  └────────┬─────────┘          └────────────┬──────────────┘  │
└───────────┼─────────────────────────────────┼─────────────────┘
            │ POST /chat (SSE stream)         │ GET /admin/*
┌───────────▼─────────────────────────────────▼─────────────────┐
│                    FastAPI Backend (Render)                   │
│                                                               │
│  ┌─────────────────────── Agent Loop ─────────────────────┐   │
│  │  app/agent.py                                          │   │
│  │  1. load conversation history + system prompt          │   │
│  │  2. call LLM (app/llm.py)                              │   │
│  │  3. if tool_use → policy check → execute → loop        │   │
│  │  4. else → stream final answer                         │   │
│  └──────┬──────────────┬──────────────┬───────────────────┘   │
│         │              │              │                       │
│  ┌──────▼─────┐ ┌──────▼─────┐ ┌──────▼──────────┐            │
│  │ Retrieval  │ │  Tools     │ │  Policy Engine  │            │
│  │ app/rag.py │ │ app/tools/ │ │  app/policy.py  │            │
│  │ (KB chunks │ │ get_order  │ │  refund limits, │            │
│  │  + cosine) │ │ refund     │ │  escalation     │            │
│  │            │ │ address    │ │  rules (pure    │            │
│  │            │ │ warranty   │ │  Python)        │            │
│  │            │ │ escalate   │ │                 │            │
│  └──────┬─────┘ └──────┬─────┘ └──────┬──────────┘            │
│         │              │              │                       │
│  ┌──────▼──────────────▼──────────────▼──────────┐            │
│  │              SQLite (SQLAlchemy)               │            │
│  │  customers · orders · order_items · products   │            │
│  │  kb_docs · kb_chunks(embedding)                │            │
│  │  conversations · messages                      │            │
│  │  events (append-only) · escalations            │            │
│  └────────────────────────────────────────────────┘           │
└───────────────────────────────────────────────────────────────┘
                          │
                    Claude API (tool use)
```

## The agent loop (heart of the system)

```
def run_turn(conversation_id, user_message):
    history = load_messages(conversation_id)
    context = retrieve_kb(user_message)          # top-4 chunks + scores
    messages = build(system_prompt, context, history, user_message)

    for step in range(MAX_STEPS := 6):
        resp = llm.complete(messages, tools=TOOL_SCHEMAS)
        if resp.stop_reason != "tool_use":
            return stream(resp.text)              # final answer

        for call in resp.tool_calls:
            decision = policy.check(call)         # ALLOW / DENY / ESCALATE
            log_event(call, decision)
            if decision is ESCALATE:
                return escalate(conversation_id, reason=decision.reason)
            result = execute(call) if decision is ALLOW else decision.message
            messages.append(tool_result(call.id, result))
```

Rules baked into the loop:
- **Policy gate before execution, always.** The LLM never directly mutates state.
- **Max 6 tool steps** per turn → no runaway loops, bounded cost.
- **Low retrieval confidence** (top score < 0.35) injects an instruction: "you don't have reliable information; offer escalation" — prevents hallucinated policy answers.
- **Idempotency:** `initiate_refund` is keyed on `(order_id, conversation_id)`; retries can't double-refund.

## Data model (core tables)

- `customers(id, name, email, phone)`
- `orders(id, customer_id, status, total, placed_at, delivered_at, payment_method)`
- `order_items(order_id, product_id, qty, price)`
- `products(id, name, category, price, warranty_months)`
- `refunds(id, order_id, amount, status, initiated_by, conversation_id, created_at)`
- `kb_chunks(id, doc_id, text, embedding BLOB, section)`
- `conversations(id, customer_id, status[active|resolved|escalated], created_at)`
- `messages(id, conversation_id, role, content, created_at)`
- `events(id, conversation_id, type[tool_call|policy_decision|retrieval|escalation], payload JSON, created_at)`
- `escalations(id, conversation_id, reason, summary, sentiment, suggested_action, status[open|claimed], created_at)`

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Send message; SSE stream of tokens + structured `action` events (e.g., `refund_initiated`) |
| `GET /conversations/{id}` | Resume conversation |
| `POST /auth/demo` | Pick a demo customer identity (no real auth — deliberate scope cut, noted in README) |
| `GET /admin/metrics` | Resolution rate, escalation rate, avg tool calls/conversation, intents |
| `GET /admin/escalations` | The human queue with handoff packets |
| `GET /admin/conversations/{id}/trace` | Full event trace — the "glass box" view for judges |
| `POST /evals/run` (dev only) | Trigger eval suite |

## Security & guardrail posture

- Prompt-injection resistance: KB chunks and tool results are wrapped in delimiters and the system prompt instructs the model to treat them as data; the *real* defense is that policy checks are Python, so injected text can at most make the agent *ask* for a disallowed refund, which policy denies.
- No secrets in repo; CORS locked to the Vercel domain; rate limit of 20 messages/min per session (protects the API budget during judging).
- Customer can only access their own orders: tools take `customer_id` from the server-side session, never from LLM output.
