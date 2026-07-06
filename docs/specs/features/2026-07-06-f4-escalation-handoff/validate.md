# F-004 — Validation Record

## Automated tests

`uv run pytest tests/ -v` — 69/69 passed (F-001 through F-003's 53, plus 16 new).
`uv run ruff check app data tests` — all checks passed.

| File | Covers |
|---|---|
| `tests/test_escalation_packet.py` | `attempted_actions_from_events` — tool_call listing, non-ALLOW policy decisions, ALLOW dedup, chronological/conversation scoping |
| `tests/test_handoff_packet.py` | `build_handoff_packet` — LLM-derived summary/sentiment/suggested_action, attempted_actions always from events (never the LLM's own), graceful fallback on bad JSON |
| `tests/test_create_escalation.py` | `create_escalation` — row creation, conversation status flip, reference/message format, event logging |
| `tests/test_escalation_triggers.py` | all 4 acceptance criteria below, plus the low-confidence trigger, via a fake `llm_complete` (no network calls) |
| `tests/test_agent.py` (updated) | existing ESCALATE-path test updated for the new two-call (main loop + packet) flow |

## Acceptance criteria (from spec.md)

**1. ₹8,000+ refund request → escalation with reason OVER_LIMIT and a correct suggested action.**

PASS — `test_refund_over_ceiling_escalation_has_correct_reason_and_nonempty_suggested_action`.
A ₹8,499 refund request produces `escalation_reason == "OVER_LIMIT"` and an `Escalation`
row whose `suggested_action` reflects the LLM-provided guidance (order qualifies on
every rule except amount).

**2. "talk to a human" → immediate escalation, no argument from the agent.**

PASS — `test_explicit_human_request_escalates_immediately_without_agent_argument`. The
`escalate_to_human` tool call short-circuits straight to `create_escalation` in the same
loop iteration — no further LLM reasoning call is made before escalating (only the one
additional call for the handoff packet itself).

**3. Packet's `attempted_actions` exactly matches logged events for that conversation.**

PASS — `test_handoff_packet_attempted_actions_exactly_matches_logged_events`. After a
`get_customer_orders` call followed by an over-limit `initiate_refund` attempt, the
stored `Escalation.attempted_actions` is asserted equal to an independently computed
`escalation.attempted_actions_from_events(session, conversation_id)` call — not just
"non-empty" or "plausible," but byte-for-byte identical to what the event log says
happened.

**4. After escalation, the customer can still ask an unrelated question and get a normal answer.**

PASS — `test_customer_can_ask_an_unrelated_question_after_escalation`. A second
`run_turn` call in the same conversation (after escalation flipped `Conversation.status`
to `"escalated"`) returns `escalated=False` and a normal grounded answer — `run_turn`
never consults conversation status before processing, so escalation never blocks
further chat.

## Additional coverage beyond the 4 named criteria

- **Trigger 2 (low-confidence retrieval)**: `test_low_confidence_kb_search_escalates` —
  a `search_kb` call returning `low_confidence=True` escalates with reason
  `LOW_CONFIDENCE`.
- **Trigger 5 (loop safety)**: unchanged from F-002/F-003, now routed through
  `create_escalation` instead of a bare message (not given a dedicated new test since
  F-002 already covers the 6-step ceiling structurally).

## Out-of-scope check

No human-reply UI, SLA timers, notification/email delivery, or reassignment logic were
added — `Escalation.status` starts and stays `"open"`; there is no code path that
changes it to `"claimed"` (that's F-005's queue UI). Sentiment trigger (#4, marked
cut-line candidate in spec.md) intentionally not implemented — see implementation.md.

## Verdict

4/4 acceptance criteria PASS. Feature complete per spec, with the sentiment trigger
explicitly and deliberately cut.
