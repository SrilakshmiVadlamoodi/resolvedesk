# F-007 — Validation Record

## Automated tests

`uv run pytest tests/ -v` — 88/88 passed (F-001 through F-004's 69, plus 19 new).
`uv run ruff check app data tests` — all checks passed.

| File | Covers |
|---|---|
| `tests/test_auth.py` | signed token round-trip, tamper/garbage/empty rejection, no shared server state needed to resolve |
| `tests/test_ratelimit.py` | sliding-window allow/block, per-token independence, window expiry |
| `tests/test_pending_action_persistence.py` | confirmation surviving a simulated restart, single-use nonce, expired nonce |
| `tests/test_api_chat.py` | AC1, AC2, AC3, AC4, AC6, AC7 (see below) |
| `tests/test_api_restart.py` | AC5 |
| `tests/test_agent.py` / `test_policy.py` / etc. (unchanged) | confirm the `PendingAction` refactor didn't regress F-002–F-004 |

## Acceptance criteria (from spec.md)

**1. A fresh `POST /chat` with no `conversation_id` creates a conversation, streams a grounded answer, and both the user and assistant messages exist in `messages` afterward.**

PASS — `test_fresh_chat_creates_conversation_and_persists_both_messages`. Response
contains `conversation`/`token`/`done` SSE events; `messages` table has exactly one
`user` row (the question) and one `assistant` row (the grounded answer).

**2. Reloading the page and calling `GET /conversations/{id}` returns the full prior history, and a follow-up `POST /chat` on that id continues the conversation with context intact.**

PASS — `test_reload_then_continue_conversation_with_context_intact`. After the first
turn, `GET /conversations/{id}` returns 2 messages; a follow-up `POST /chat` on the
same `conversation_id` succeeds and the history grows to 4 messages — proven again,
independently, across a simulated process restart in `test_api_restart.py`.

**3. A write action (refund) emits `confirmation_request`, executes only after `POST /chat/confirm` with the correct nonce, and a replayed/expired nonce is rejected with a typed error, not a duplicate refund.**

PASS — `test_refund_confirmation_flow_and_replayed_nonce_rejected` (replay) and
`tests/test_pending_action_persistence.py::test_expired_nonce_is_rejected` (expiry,
5-minute TTL). Both produce a typed `error` SSE event / `TurnResult.error` code
(`NONCE_NOT_FOUND` / `NONCE_EXPIRED`) and leave the `refunds` table with exactly one row
regardless of how many times the nonce is replayed.

**4. Requesting another customer's `conversation_id` (guessed or enumerated) returns 404.**

PASS — `test_requesting_another_customers_conversation_returns_404`. `_get_owned_conversation`
returns 404 (never 403) whenever `conversation.customer_id != customer_id`, matching
the spec's "don't reveal that the id exists" requirement.

**5. Killing and restarting the backend process mid-conversation, then continuing the chat, produces no loss of context and no duplicate messages.**

PASS — `test_killing_and_restarting_the_backend_preserves_conversation_and_avoids_duplicates`.
Two independent SQLAlchemy engines (`engine.dispose()`'d between them, zero shared
Python state) against the same SQLite file: conversation history is intact after
"restart," and the message count after a follow-up turn is exactly 4 (2 old + 2 new) —
no duplication.

**6. Exceeding the rate limit returns a typed `error` SSE event the frontend can render as a friendly message, not a raw connection drop.**

PASS — `test_exceeding_rate_limit_returns_typed_error_event`. With `RateLimiter(limit=1)`
injected, the second `/chat` call in the same window returns HTTP 200 with an
`event: error` / `RATE_LIMITED` SSE payload (never a bare 429 or dropped connection).

**7. Every `POST /chat` and `POST /chat/confirm` call produces at least one corresponding `events` row, verifiable directly against the admin trace view (F-005).**

PASS — `test_every_chat_call_produces_at_least_one_event_row`. Even a simple Q&A with
no tool calls logs at least a `retrieval` event (F-001's `rag.retrieve` always logs
one); tool-using and rate-limited calls log additional `tool_call`/`policy_decision`/
`rate_limited` events on top.

## Out-of-scope check

No real authentication, no multi-device session sync, no message editing/deletion, no
backend typing-indicator concept, no history pagination — `GET /conversations/{id}`
loads the full history unconditionally, matching the spec's explicit "fine for a
hackathon-scale demo" allowance.

## Verdict

7/7 acceptance criteria PASS. Feature complete per spec, with the demo-token mechanism
and streaming granularity documented as deliberate interpretations in
implementation.md.
