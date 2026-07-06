# Backlog — ResolveDesk

Not in scope for the 12-day build. Parked here so it doesn't get lost or
accidentally re-scoped in on a day-9 burst of ambition. Nothing here should be
started unless the roadmap is explicitly amended.

## Cut lines (from roadmap.md — cut in this order if behind schedule)

1. Warranty-claim tool — refund flow already demonstrates write-actions.
2. Trace view in the admin dashboard — keep metrics + escalation queue.
3. Sentiment-based escalation — keep rule-based triggers only.
4. Eval suite shrinks 50 → 25 scenarios — never cut to zero, it's the differentiator.

Never cut: policy engine, escalation, the refund flow, deployment, the video.

## F-001 — Knowledge base / RAG

- Vector DB (currently in-memory/cosine over seed-time embeddings)
- Reranking models
- Multi-language KB
- KB admin UI — edit markdown + reseed instead

## F-002 — Agent tool calling

- Parallel tool calls
- Agent frameworks (LangChain, etc.)
- Dynamic tool discovery / MCP — mention as future work in README only

## F-003 — Refund policy engine

- Partial / item-level refunds
- Store credit
- ML-based fraud scoring

## F-004 — Escalation & handoff

- Human reply UI (agent-side chat for the human agent)
- SLA timers
- Notifications / email
- Reassignment between human agents

## F-005 — Admin dashboard

- Auth / roles
- Date-range filters
- CSV export
- CSAT collection

## F-006 — Eval suite

- Latency benchmarking
- Cost tracking dashboards
- Regression history over time

## V2 hardening (post-hackathon, not demo-relevant)

- Real vector DB + reranking once KB size outgrows in-memory cosine search
- Proper auth/roles instead of demo-identity auth
- SLA timers and notification pipeline for escalations
- Multi-agent handoff and reassignment workflow
- Cost and latency tracking dashboards, regression history for evals
