# F-002 — Implementation Notes

## What was built

Since none of the domain/agent infrastructure existed yet, this feature also stood up
the prerequisites the spec's tools depend on:

- **Domain models** (`app/models.py`): `Customer`, `Product`, `Order`, `OrderItem`,
  `Refund` — matching architecture.md's data model.
- **Seed fixture** (`data/seed.py:seed_domain`): 2 customers, 3 products, 3 orders
  (`delivered`, `shipped`, and one on a *different* customer, for scoping tests).
  Idempotent, same delete-then-insert pattern as F-001's `seed_kb`.
- **Tools** (`app/tools/`), one file each, all exporting `NAME`, `SCHEMA`
  (Anthropic-shaped JSON schema), `REQUIRES_CONFIRMATION`, `execute(session,
  customer_id, **kwargs)`:
  - `get_customer_orders`, `get_order_details`, `search_kb` (read, no confirmation;
    `search_kb` wraps F-001's `rag.retrieve`)
  - `initiate_refund`, `update_shipping_address`, `file_warranty_claim` (write,
    confirmation required)
  - `escalate_to_human` (control, no confirmation)
  - `app/tools/__init__.py` — `TOOLS` (name → module) and `TOOL_SCHEMAS` registry.
  - Every read/write tool re-derives `customer_id`-scoped orders from the DB itself
    (defense in depth) — `customer_id` is a parameter injected by the loop, never
    read from LLM-supplied arguments.
- **Policy gate** (`app/policy.py`): `PolicyDecision(outcome, reason,
  customer_message)` plus `check_refund`, `check_address_change`, and a `check(tool_name,
  arguments, session, customer_id)` dispatcher used by the loop. `check_refund`'s rules
  (ceiling ESCALATE, duplicate-refund ESCALATE) are **provisional** — F-003 owns the
  full ruleset and will replace `check_refund`'s body without changing this contract.
- **Agent loop** (`app/agent.py`): `run_turn()` builds `<kb_context>`-wrapped system
  prompt from F-001 retrieval, then loops LLM call → policy check → execute/pause →
  append result, max 6 steps. `confirm_action()` resumes a paused write-tool call after
  the customer confirms. Pending confirmations are held in an in-memory
  `dict[nonce, _PendingAction]` (not the DB — a nonce is a within-process handle, not
  durable state that needs to survive a restart mid-confirmation for the hackathon
  scope).
- **LLM layer** (`app/llm.py`): real `anthropic` SDK call. `_to_anthropic_messages()`
  converts our provider-agnostic message list (`system`/`user`/`assistant`/`tool`
  roles) into Anthropic's `(system, messages)` shape — the one place a provider swap
  would touch.

## Key decisions

- **Policy checks always run, even for tools that don't mutate anything** (read tools
  hit `check()`'s default `ALLOW` branch). This keeps the loop's control flow uniform —
  no special-casing "does this tool need a policy check" — and means every tool call
  produces a `policy_decision` event for free.
- **Confirmation is orthogonal to policy.** A tool can be `ALLOW`ed by policy and still
  pause for confirmation (the normal refund case); or be `ESCALATE`d and never reach the
  confirmation step at all (the prompt-injection case). This is why AC4 doesn't need a
  customer to reject anything — the escalation happens before confirmation is offered.
- **In-memory pending-action store**, not a DB table. Simplest thing that satisfies the
  spec's "pending action is stored server-side with a nonce" — a `conversations`/
  `pending_actions` table can replace it later without changing `agent.py`'s public
  functions if multi-process deployment ever needs it.
- **`_to_anthropic_messages` is unit-tested; `llm.complete` is not.** The conversion
  logic is pure and deterministic; the actual API call is the one true external I/O
  boundary in this feature, consistent with TDD's guidance to mock/skip only the
  unavoidable edge, not the logic around it. All five agent-loop acceptance criteria
  are verified with a fake `llm_complete` callable — no network calls in the test
  suite.

## Deviations from spec

None in tool set or loop behavior. One scope note: conversation/message persistence
(mentioned in roadmap.md's Day 5, not in this spec) is intentionally **not** built here
— `run_turn()` takes `history` as a plain list the caller supplies. No `POST /chat`
SSE endpoint was built either; the spec's acceptance criteria are about tool-calling
and policy-gating behavior, which are fully exercised through `agent.run_turn`/
`confirm_action` directly. Wiring those into FastAPI + SSE is routing/plumbing, not
agent-loop logic, and is deferred to whichever feature adds the chat API surface.

## Follow-ups (not blocking F-002)

- `app/policy.py`'s refund ceiling (₹8,000) and duplicate-refund rule are provisional;
  F-003 replaces them with the full window/category/idempotency ruleset from
  spec.md.
- No `POST /chat` / `POST /chat/confirm` HTTP routes yet — `agent.run_turn` /
  `confirm_action` are ready to be wired to FastAPI + SSE.
- `file_warranty_claim` is on the roadmap's cut-line list; kept in since the spec table
  didn't exclude it and it was cheap to include.
