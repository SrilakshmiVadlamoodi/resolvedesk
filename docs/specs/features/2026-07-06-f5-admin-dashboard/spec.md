# F-005 — Admin Dashboard

## Goal
Show the *business* view — proof that this is a product, not a chat demo. Entirely a read model over the `events`, `conversations`, and `escalations` tables.

## Views
1. **Metrics tiles** (`GET /admin/metrics`)
   - Resolution rate (resolved / total conversations)
   - Escalation rate + breakdown by reason (pie)
   - Actions taken (refunds initiated, addresses updated) with total refund value
   - Avg tool calls per conversation, avg messages to resolution
2. **Intent breakdown** — bar chart of conversation intents (order_status, refund, warranty, product_question, other), tagged by one cheap LLM classification per conversation at close/escalation.
3. **Escalation queue** — from F-004, with handoff packets and Claim.
4. **Conversation trace** (`/admin/conversations/{id}/trace`) — timeline of messages, retrievals (chunks + scores), tool calls (args + results), policy decisions, escalation. *This is the "glass box" judges get shown when they ask "how does it work?"*

## Behavior
- Read-only except Claim; no auth beyond a static demo token in the URL (`?key=demo`) — noted as a deliberate scope cut.
- Seed script generates ~15 synthetic completed conversations so the dashboard looks alive on first load (clearly labeled "sample data" in UI).
- Auto-refresh every 10 s so the demo shows the metrics tick when a refund happens live.

## Acceptance criteria
1. Initiating a refund in the chat visibly updates "Actions taken" within one refresh.
2. Every number on the dashboard is derivable from `events` (no separate counters that can drift).
3. Trace view for the demo refund conversation shows: retrieval → get_order_details → policy ALLOW → initiate_refund → action event, in order.

## Out of scope
Auth/roles, date-range filters, CSV export, CSAT collection.
