# ResolveDesk — Project Constitution

ResolveDesk is an agentic customer-support platform built solo for FlowZint AI Hackathon 2026 (Support Chat Bot category). It resolves customer issues end-to-end for a fictional D2C electronics store ("VoltKart") — answering from a knowledge base, taking real actions (order lookup, refunds, address changes) via tool calls, and escalating to humans with full context when it can't or shouldn't act.

## Non-negotiable principles

1. **Spec first, code second.** Every feature has a spec in `docs/specs/features/<date>-f<n>-<name>/spec.md` before implementation begins. If implementation reveals the spec is wrong, update the spec in the same PR/commit.
2. **The agent never acts outside policy.** All money-touching actions (refunds) go through the policy engine (`app/policy.py`). The LLM proposes; the policy engine disposes. An LLM response alone is never sufficient authorization for a state-changing action.
3. **Every claim is grounded.** Answers about policies, products, or orders must come from a tool result or a retrieved KB chunk. If retrieval confidence is low, the agent says it doesn't know and escalates — it never guesses.
4. **Demo-critical paths are sacred.** The three demo flows (order status, in-policy refund, escalation) must pass the eval suite on every commit after Day 6. If a change breaks them, revert first, debug second.
5. **Timebox ruthlessly.** This is a 12-day hackathon. Any feature not in `docs/specs/roadmap.md` is out of scope. Write it in `docs/specs/backlog.md` and move on.

## Working rules for Claude Code

- Read `docs/specs/mission.md`, `docs/specs/tech-stack.md`, and the relevant feature spec (`docs/specs/features/<date>-f<n>-<name>/spec.md`) before implementing anything.
- Backend code lives in `app/`, frontend in `web/`, eval suite in `evals/`, seed data in `data/`.
- Python: type hints everywhere, Pydantic models for all API request/response bodies, no bare `except`.
- Never hardcode the LLM provider. All model calls go through `app/llm.py` so the provider can be swapped with one change.
- All tools the agent can call are defined in `app/tools/` — one file per tool, each with: a JSON schema, an execute function, and a `requires_confirmation` flag.
- SQLite via SQLAlchemy. Schema changes require updating `data/seed.py` so the demo database stays reproducible with one command.
- Every tool execution and escalation is written to the `events` table — the dashboard is built entirely from this table.
- Secrets only via environment variables (`.env`, gitignored). The repo must be safe to make public — it goes on the resume.
- Commit after each working increment with conventional-commit messages (`feat:`, `fix:`, `spec:`).

## Definition of done (per feature)

A feature is done when: (a) its spec's acceptance criteria pass, (b) relevant eval scenarios pass, (c) it works in the deployed environment, not just localhost, (d) it appears in the demo script if demo-relevant.

## Style

- Responses from the agent to customers: warm, concise, no corporate filler, always states what action it took ("I've initiated a refund of ₹1,499 to your original payment method — you'll see it in 5–7 business days").
- Errors shown to customers never leak stack traces or internal tool names.
