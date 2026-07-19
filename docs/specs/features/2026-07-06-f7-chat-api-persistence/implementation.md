# F-007 — Implementation Notes

## What was built

- **`app/auth.py`** — demo identity as a stateless, self-describing signed token
  (`customer_id + HMAC-SHA256(customer_id)`), not a server-side `session_token ->
  customer_id` map. This was a deliberate deviation from the spec's literal wording
  ("server stores session_token -> customer_id mapping") — see Key Decisions.
- **`app/ratelimit.py`** — in-memory sliding-window `RateLimiter` (20/min per token),
  used as a FastAPI dependency so tests can inject a tighter limit.
- **Models**: `Message` (conversation_id, role, content, created_at), `PendingAction`
  (nonce PK, conversation_id, customer_id, tool_name, arguments, call_id, messages,
  actions, steps_used, created_at), `Conversation.updated_at`.
- **`app/agent.py` refactor**: the in-memory `_PENDING` dict from F-002 is replaced
  with the `PendingAction` table. `confirm_action` now also **re-runs `policy.check`**
  before executing (per spec section 3 — "never trust that confirmed by customer alone
  is sufficient authorization"), handles the DENY/ESCALATE outcomes identically to the
  main loop, deletes the row on lookup (single-use), and rejects with a typed
  `TurnResult.error` (`NONCE_NOT_FOUND` / `NONCE_EXPIRED`) rather than silently no-opping.
  This changed `TurnResult` (added an `error: str | None` field) but not its existing
  fields, so all of F-002 through F-004's tests kept passing unmodified.
- **`app/api.py`** — the HTTP surface: `POST /auth/demo`, `POST /chat`, `POST
  /chat/confirm`, `GET /conversations/{id}`. Dependency-injected `get_db`,
  `get_llm_complete`, `get_rate_limiter` so tests can override each independently
  (in-memory DB, fake LLM, tight rate limit) without touching real network or real
  time.

## Key decisions

- **Stateless signed token instead of a server-side token store.** The spec's literal
  wording implies an in-memory or DB-backed `session_token -> customer_id` table. A
  self-describing signed token needs no such table at all, and — importantly — trivially
  satisfies "the token keeps working across a server restart" for free, which a
  pure-in-memory token store would not (and a DB-backed one would add a whole table for
  something with zero real security requirements, per the spec's own "no real auth"
  framing). Documented here as a conscious interpretation, not a shortcut.
- **`Message` rows only for user/assistant turns, not the mid-turn tool-call
  transcript.** A single `POST /chat` call runs the whole agent loop synchronously
  (read tool calls, policy checks, possibly a write-tool pause) within one request; the
  `messages` table only needs to reconstruct *conversation-level* history (what did the
  customer ask, what did the agent finally answer) for the next turn's context, not the
  tool-call blow-by-blow — that's already fully captured in `events`
  (`tool_call`/`policy_decision` rows), which is the system of record for that anyway
  (per F-004's explicit "attempted_actions comes from events, not memory" rule). This
  keeps `history` passed into `run_turn` a simple list of `{role, content}` dicts,
  matching the format F-002's tests already used.
- **No real token-by-token streaming.** `app/llm.py:complete()` is a single blocking
  Anthropic call (F-002's design), so the `token` SSE event carries the whole final
  answer as one chunk rather than incremental deltas. Real incremental streaming would
  mean switching `llm.py` to Anthropic's streaming API — a deeper F-002 change, out of
  this spec's stated scope (it wraps the loop, not reimplement it). Documented as a
  known simplification, not hidden.
- **`action` SSE events are synthesized from `TurnResult.actions`**, mapping tool name
  to a public event type (`initiate_refund` → `refund_initiated`, etc.) and merging
  the original arguments with the tool's result — reasonably matches the spec's example
  shape without inventing new fields on the tool layer itself.
- **API-layer tests were written after `app/api.py`, not before** — a deliberate,
  acknowledged exception to strict TDD. `app/api.py` is thin routing/persistence glue
  over already-TDD'd business logic (`agent.run_turn`, `policy.check`,
  `escalation.create_escalation`); getting FastAPI's dependency-override wiring right
  first, then locking it down with integration tests covering every acceptance
  criterion, was more direct than TDD-ing HTTP plumbing method-by-method. All the
  actual decision logic underneath was TDD'd in F-002/F-003/F-004.
- **Restart-safety proof uses two separate SQLAlchemy engines against the same SQLite
  file** (`tests/test_api_restart.py`, `tests/test_pending_action_persistence.py`),
  with `engine.dispose()` between them and zero shared Python objects — the closest
  faithful simulation of "kill and restart the process" available without actually
  spawning a second process in the test suite.

## Deviations from spec

- Demo-token storage mechanism (signed/stateless vs. server-side map) — see above.
- No real per-message token-by-token SSE streaming — see above.

## Post-hoc fix: LLM call-site errors were surfacing as raw 500s

Found during F-009 (chat UI) manual verification: `_run_loop`'s `llm_complete(...)`
call (in `app/agent.py`, invoked from both `run_turn` and `confirm_action`) had no
error handling, so a provider/network failure — missing API key, timeout, upstream API
error — propagated as an unhandled exception and FastAPI returned a bare `Internal
Server Error`, not the typed `error` SSE event AC6 requires. Only the rate-limit path
had a typed error; a failed LLM call did not.

Fixed with a narrow `try/except Exception` around that one call site: catches the
failure, logs an `llm_error` event (server-side only, includes the raw exception string
for debugging — never sent to the customer), and returns
`TurnResult(error="LLM_UNAVAILABLE", text="I'm having trouble connecting right now —
please try again in a moment.")`, which `_turn_result_to_sse` already turns into a
typed `error` SSE event via the existing `elif result.error:` branch — no changes
needed to `app/api.py` itself.

This also required a one-line fix to `evals/runner.py`: it previously relied on the
exception *propagating* to flag a broken LLM call as a scenario failure; since
`agent.py` now catches it internally, `run_scenario` gained an explicit
`if last_result.error: return ScenarioResult(..., passed=False, ...)` check so a
broken-LLM eval scenario still fails the suite instead of silently passing.

Tests: `tests/test_agent.py::test_llm_failure_returns_typed_error_not_a_crash`,
`::test_llm_failure_still_logs_an_event`;
`tests/test_api_chat.py::test_llm_failure_returns_typed_error_event_not_a_500`;
`tests/test_eval_runner.py::test_an_exception_from_llm_complete_is_recorded_as_a_failure_not_raised`
(pre-existing, updated expectation to match the new `detail` payload field rather than
a raised exception's message).

## Follow-ups (not blocking F-007)

- `PendingAction` rows are never garbage-collected once expired (only deleted on
  lookup). Fine at hackathon scale; a cron/sweep would be needed for a long-running
  deployment.
- Admin dashboard (F-005) will want to read from `events`/`escalations` alongside this
  feature's `conversations`/`messages` — no conflicts expected since this feature only
  adds rows, never mutates F-004/F-005's tables.
