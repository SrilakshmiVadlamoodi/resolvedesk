# F-005 — Validation Record

## Automated tests

`uv run pytest tests/ -v` — 117/117 passed (F-001 through F-007's 88, plus 29 new).
`uv run ruff check app data tests` — all checks passed.

| File | Covers |
|---|---|
| `tests/test_admin_metrics.py` | `build_metrics` — resolution/escalation rates, reason breakdown, actions taken + refund value derived from `tool_call` events, avg tool calls/conversation, avg turns to resolution, empty-DB safety |
| `tests/test_admin_trace.py` | `build_trace` — chronological order, conversation scoping, empty result for unknown id |
| `tests/test_intent.py` | `classify_intent` — LLM-derived label, fallback to `other`, case-insensitivity, no-messages case |
| `tests/test_escalation_claim.py` | `claim_escalation` — flips status, 404-equivalent `None` for unknown id, idempotent re-claim |
| `tests/test_admin_api.py` | all four admin routes: demo-key gate (401), metrics, escalations list + claim, trace 404 |
| `tests/test_seed_admin_demo.py` | `seed_admin_demo_data` — ~15 conversations, resolved/escalated mix, one `Escalation` row per escalated conversation, events usable by `build_metrics`, idempotent rerun |
| `tests/test_admin_dashboard_e2e.py` | AC1 and AC3 end-to-end (see below) |

## Acceptance criteria (from spec.md)

**1. Initiating a refund in the chat visibly updates "Actions taken" within one refresh.**

PASS — `test_refund_via_chat_updates_actions_taken_metric`. A full `POST /chat` →
`POST /chat/confirm` refund flow through the real chat API, followed immediately by
`GET /admin/metrics?key=demo`: `refunds_initiated` goes from 0 to 1 and
`total_refund_value` reflects the exact amount (₹2,999) — no polling/refresh delay
needed since metrics are computed live from `events` on every request.

**2. Every number on the dashboard is derivable from `events` (no separate counters that can drift).**

PASS by construction — `app/admin_metrics.py` imports only `Conversation`, `Escalation`,
and `Event`; it has no import of `Refund`, `Order`, or any other model, so there is no
code path by which a metric could read a value that isn't in one of the three allowed
tables. `total_refund_value`/`refunds_initiated`/`addresses_updated` are summed directly
from `tool_call` event payloads, not from a `Refund` table count.

**3. Trace view for the demo refund conversation shows: retrieval → get_order_details → policy ALLOW → initiate_refund → action event, in order.**

PASS — `test_trace_view_shows_expected_order_for_a_refund_conversation`. Runs a real
"check order, then refund" conversation through the chat API, then asserts via
`GET /admin/conversations/{id}/trace?key=demo` that the event indices satisfy
`retrieval < get_order_details(tool_call) < initiate_refund(policy_decision, ALLOW) <
initiate_refund(tool_call)` — the exact sequence named in the spec.

## Out-of-scope check

No auth/roles beyond the static `?key=demo` check, no date-range filters, no CSV
export, no CSAT collection — none of these were added.

## Verdict

3/3 acceptance criteria PASS. Backend read-model and API complete per spec; the React
frontend dashboard UI (charts, auto-refresh, Claim button) was not built in this pass —
see implementation.md.
