# F-005 — Implementation Notes

## What was built

- **`app/admin_metrics.py`**:
  - `build_metrics(session)` — resolution rate, escalation rate + reason breakdown,
    actions taken (refunds initiated, addresses updated, total refund value), avg tool
    calls per conversation, avg turns to resolution. Reads only `conversations`,
    `escalations`, and `events` — never `refunds`/`orders` directly, per the spec's
    "no separate counters that can drift" requirement (AC2). "Avg turns to resolution"
    is derived from the count of `retrieval` events per closed conversation, since
    F-001's `rag.retrieve()` logs exactly one retrieval event per user turn — a
    faithful proxy for "messages" without needing to read the `messages` table (which
    the spec's Goal doesn't list as an allowed source).
  - `build_trace(session, conversation_id)` — the full ordered event timeline for one
    conversation (the "glass box" view).
- **`app/intent.py`** — `classify_intent()`: one LLM call per conversation, classifying
  into `order_status | refund | warranty | product_question | other`, falls back to
  `other` for any unparseable/unexpected response, logs an `intent` event. Wired into
  `escalation.create_escalation()` (F-004) — escalation is currently the only "close"
  trigger the system has, so that's where the classification fires today.
- **`app/escalation.py:claim_escalation()`** — flips an `Escalation` row from `open` to
  `claimed`; idempotent (claiming twice is a no-op, not an error).
- **`app/admin_api.py`** — `GET /admin/metrics`, `GET /admin/escalations`,
  `POST /admin/escalations/{id}/claim`, `GET /admin/conversations/{id}/trace`, all
  behind a `require_demo_key` dependency checking `?key=demo` — no real auth, per spec.
- **`data/seed.py:seed_admin_demo_data()`** — 15 synthetic conversations (8 resolved,
  7 escalated across 5 different escalation reasons) with plausible retrieval/tool_call/
  policy_decision/escalation/intent events, so the dashboard looks alive on first load.
  Idempotent (delete-then-reinsert), wired into `main()` alongside `seed_kb`/`seed_domain`.

## Key decisions

- **Intent classification only fires on escalation, not on a generic "conversation
  closed" event.** The spec says classification happens "at close/escalation," but no
  code path in F-002 through F-004 ever marks a conversation `resolved` — that concept
  doesn't exist yet (conversations only ever go `active` → `escalated`). Rather than
  invent a "resolve" mechanic un-specified by any feature, intent tagging is wired to
  the one real close event that exists. Documented as a scope-matched decision, not an
  oversight — a future "mark resolved" feature can call `classify_intent` the same way.
- **Wiring `classify_intent` into `create_escalation` added one more required
  `llm_complete` response to every escalation flow's fake-LLM sequence in F-002/F-004's
  existing tests** (6 call sites across `test_agent.py` and
  `test_escalation_triggers.py`). Each got one appended canned response
  (`LLMResponse(content="refund"/"other", tool_calls=[])`) rather than being restructured
  — a mechanical, low-risk change since the intent-classification call is independent of
  everything those tests were actually asserting.
- **No React dashboard UI was built.** Consistent with F-002 and F-007 before it, this
  pass implements the backend read-model API only — `app/admin_api.py`'s four endpoints
  are ready for the `web/` React app to consume (metrics tiles, pie/bar charts, escalation
  queue, trace view, 10s auto-refresh), but that frontend work wasn't started. Flagged
  explicitly rather than silently left undone.
- **Synthetic seed data is fully self-contained (no real LLM calls)** — `seed_admin_demo_data`
  hand-writes plausible event payloads instead of running the real agent loop 15 times,
  keeping `python -m data.seed` fast, free, and deterministic. It reuses the exact event
  *shapes* (`tool_call`/`policy_decision`/`escalation`/`intent` payloads) that the real
  loop produces, so `build_metrics`/`build_trace` don't need to special-case sample data.

## Deviations from spec

- Frontend dashboard UI (charts, auto-refresh, Claim button) not built — backend API
  only. See "Key decisions."

## Follow-ups (not blocking F-005)

- No date-range filtering, CSV export, or CSAT — all explicitly out of scope per spec.
- `web/` React dashboard consuming these four endpoints.
- When a "conversation resolved" mechanic is eventually built, wire `classify_intent`
  into that close path too, not just escalation.
