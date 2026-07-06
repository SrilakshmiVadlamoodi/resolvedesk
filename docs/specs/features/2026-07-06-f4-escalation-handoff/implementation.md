# F-004 — Implementation Notes

## What was built

- **`app/models.py`**: `Conversation` (id, customer_id, status — active/resolved/escalated)
  and `Escalation` (conversation_id, reason, summary, sentiment, attempted_actions JSON,
  suggested_action, status — open/claimed).
- **`app/escalation.py`**:
  - `attempted_actions_from_events(session, conversation_id)` — deterministically
    rebuilds what the agent actually did from `events` rows: executed tool calls by
    name, plus any non-`ALLOW` policy decision formatted as `"{tool} → {outcome}({reason})"`.
    `ALLOW` decisions are skipped (the matching `tool_call` event already represents
    that action — including both would double-count it).
  - `build_handoff_packet(session, conversation_id, reason, llm_complete)` — one LLM
    call asks for `summary`/`sentiment`/`suggested_action` as JSON; `attempted_actions`
    is **always** the deterministic list above, even if the LLM's JSON includes its own
    (silently discarded) — this is the spec's explicit guarantee that attempted actions
    come from the event log, not model memory. Falls back to generic text if the LLM
    response isn't valid JSON, so a malformed model reply can't crash escalation itself.
  - `create_escalation(session, customer_id, conversation_id, reason, llm_complete)` —
    builds the packet, flips (or creates) the `Conversation` row to `status="escalated"`,
    inserts the `Escalation` row (`status="open"`), logs an `escalation` event, and
    returns a reference (`E-{id}`) plus the customer-facing message from spec.md's exact
    wording template.
- **`app/agent.py`** now calls `escalation.create_escalation` at every point it used to
  just return a bare message, covering 4 of the spec's 5 triggers:
  1. Policy returns `ESCALATE` (over-limit, expired window, duplicate, etc. — all of
     F-003's `ESCALATE` reasons flow through automatically).
  2. `search_kb` returns `low_confidence=True` — escalates immediately, new trigger.
  3. The LLM calls `escalate_to_human` — executes the tool (so the event log has a
     record of it), then escalates immediately, without another LLM round-trip
     ("no argument from the agent," per AC2).
  5. Loop safety: 6 steps without resolution.

## Key decisions

- **Trigger 4 (sentiment classification) is cut**, per the spec's own
  `(cut-line candidate)` annotation and the backlog's roadmap cut-line #3. No acceptance
  criterion tests it, and adding a second classification LLM call per turn is a real
  cost/latency tradeoff not justified without a demo scenario that needs it.
- **`escalate_to_human` is deliberately excluded from the generic tool-execution path.**
  Every other tool appends its result and lets the loop continue reasoning; this one
  short-circuits straight to `create_escalation` after logging its own `tool_call` event,
  because AC2 requires "no argument from the agent" — continuing the loop would let the
  model second-guess an explicit human request.
- **Reference format is `E-{escalation.id}`** — simple and unique; the spec's example
  (`#E-107`) is illustrative, not a required numbering scheme.
- **`create_escalation` calls `llm_complete` a second time** within the same turn (once
  for the main loop, once for the packet). This matches the spec's "one structured LLM
  call at escalation time" — it's one *additional* call, not folded into the main
  reasoning call, so its prompt/response shape can stay simple (plain JSON, no tool
  schema).
- **Conversation row is get-or-create by explicit id** — conversation persistence
  (message history) is still out of scope per F-002's notes; `Conversation` here exists
  only to hold the `status` field this feature needs. A future conversation-persistence
  feature can extend this same table.

## Deviations from spec

- Sentiment-trigger (#4) not implemented — see "Key decisions" above; documented, not
  silently dropped.
- Admin dashboard queue UI ("Claim" button) is F-005's job, not built here — this
  feature only creates `Escalation` rows with `status="open"`, ready for F-005 to query
  and flip to `"claimed"`.

## Follow-ups (not blocking F-004)

- No fixture in `seed_domain` currently produces a `LOW_CONFIDENCE` or
  `escalate_to_human` scenario through the full chat flow with a real (non-fake) LLM;
  worth adding to F-006's eval suite scenarios.
- `Conversation.customer_id` is currently unused beyond bookkeeping (no query filters
  by it yet) — will matter once conversation history/resumption is built.
