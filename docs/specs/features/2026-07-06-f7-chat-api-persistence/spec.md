# F-007 — Chat API & Conversation Persistence

## Why this is its own spec
F-002 (agent loop & tool calling) owns the *reasoning* — given a message and history, decide what to answer or do. It does not own how a message reaches that loop over the network, or what happens to the conversation between turns. Bundling those concerns would blur test failures (a broken SSE stream would look identical to a broken tool call from the outside) and roadmap.md referenced this plumbing without any feature spec formally claiming it. This spec closes that gap.

## Goal
Expose the agent loop over HTTP with streaming responses, and persist conversations so state survives reloads, reconnects, and server restarts.

## Scope

### 1. Demo identity
- `POST /auth/demo` — body: `{customer_id}` (or none, picks a default). Returns a session token (a signed opaque string is enough — no real auth). Server stores `session_token -> customer_id` mapping.
- Every subsequent request carries this token (header or cookie); the backend resolves it to `customer_id` server-side. **The frontend and the LLM never supply `customer_id` directly** — this is the enforcement point for the cross-customer-access rule already stated in F-002's acceptance criteria.
- No password, no real signup. Clearly labeled in the UI and README as a deliberate scope cut.

### 2. `POST /chat`
- Body: `{conversation_id: str | null, message: str}`.
- If `conversation_id` is null, create a new `conversations` row (`status="active"`, linked to the resolved `customer_id`) and return its id as the first SSE event.
- Persist the incoming user message to `messages` before invoking the agent loop.
- Invoke `run_turn()` from F-002, passing the loaded message history.
- Stream the response as SSE with typed events:
  - `token` — incremental text chunks of the answer
  - `action` — structured events for completed tool actions (e.g. `{"type": "refund_initiated", "amount": 1499, "order_id": "VK-1042"}`)
  - `confirmation_request` — a write-tool call awaiting the customer's confirmation (nonce included)
  - `escalated` — conversation handed to a human, includes escalation id
  - `done` — turn complete
  - `error` — typed, customer-safe error (no stack traces, no internal tool names)
- Persist the assistant's final message to `messages` once the turn completes, even if the client disconnects mid-stream (persistence happens server-side, not client-side).
- Rate limit: 20 messages/min per session token (per tech-stack.md's guardrail posture) — return a typed `error` event, not a raw 429 with no body, so the frontend can show a friendly message.

### 3. `POST /chat/confirm`
- Body: `{conversation_id, nonce}`.
- Looks up the pending write-action stored server-side against that nonce (created when `confirmation_request` was emitted).
- Re-runs the policy check (state may have changed since the request was issued — e.g. a second refund attempt landed in between) before executing. Never trust that "confirmed by customer" alone is sufficient authorization.
- Executes the tool, emits the same `action`/`error` SSE event types as above, appends result to conversation history.
- Nonces are single-use and expire after 5 minutes; an expired or already-used nonce returns a typed error, not a silent no-op.

### 4. `GET /conversations/{id}`
- Returns full message history (for page-reload resume) — scoped to the session token's `customer_id`; requesting another customer's conversation id returns 404, not 403 (don't reveal that the id exists).

### 5. Persistence behavior
- `conversations(id, customer_id, status[active|resolved|escalated], created_at, updated_at)`
- `messages(id, conversation_id, role[user|assistant|tool], content, created_at)`
- Every `POST /chat` and `POST /chat/confirm` call, regardless of outcome, results in at least one new `events` row (ties into F-004/F-005's event log) — this route is a producer for the event log, not a separate logging path.
- Server restart mid-conversation: history in `messages` is sufficient to resume — no in-memory-only state that a restart would lose.

## Acceptance criteria
1. A fresh `POST /chat` with no `conversation_id` creates a conversation, streams a grounded answer, and both the user and assistant messages exist in `messages` afterward.
2. Reloading the page and calling `GET /conversations/{id}` returns the full prior history, and a follow-up `POST /chat` on that id continues the conversation with context intact (multi-turn works across a real page reload, not just in-memory).
3. A write action (refund) emits `confirmation_request`, executes only after `POST /chat/confirm` with the correct nonce, and a replayed/expired nonce is rejected with a typed error, not a duplicate refund.
4. Requesting another customer's `conversation_id` (guessed or enumerated) returns 404.
5. Killing and restarting the backend process mid-conversation, then continuing the chat, produces no loss of context and no duplicate messages.
6. Exceeding the rate limit returns a typed `error` SSE event the frontend can render as a friendly message, not a raw connection drop.
7. Every `POST /chat` and `POST /chat/confirm` call produces at least one corresponding `events` row, verifiable directly against the admin trace view (F-005).

## Out of scope
Real authentication/authorization, multi-device session sync, message editing/deletion, typing indicators as a distinct backend concept (frontend-only), pagination of long histories (fine to load full history for a hackathon-scale demo).

## Where this sits in the roadmap
Belongs to Day 5 ("conversation persistence, demo-identity auth, event logging on every step") as originally noted in roadmap.md — this spec formalizes what was previously an implicit assumption. F-002 must be functionally complete (loop callable directly, e.g. via script/test) before this spec starts, since it wraps that loop rather than reimplementing it.
