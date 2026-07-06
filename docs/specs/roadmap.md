# Roadmap — ResolveDesk (12 days)

Each day ends with a working commit. Milestones M1–M4 are the "still on track?" checkpoints. Features reference specs in `specs/features/`.

## Phase 0 — Foundation (Days 1–2)

**Day 1**
- Repo init, uv project, FastAPI skeleton, SQLAlchemy models, `data/seed.py` (VoltKart: ~12 products, ~8 customers, ~25 orders in varied states: delivered, shipped, delayed, returned).
- Write the VoltKart knowledge base (~10 markdown docs: refund policy, warranty policy, shipping, product FAQs). *Writing the KB early forces policy decisions early.*

**Day 2**
- `app/llm.py` provider abstraction + smoke test.
- RAG pipeline: chunking, embedding at seed time, cosine retrieval (F-001).
- ✅ **M1: `retrieve("what is the refund window?")` returns the right chunk.**

## Phase 1 — The Agent (Days 3–5)

**Day 3**
- Agent loop v1 (no tools): system prompt + RAG context → grounded answers over `POST /chat` with SSE.

**Day 4**
- Tool framework (`app/tools/`) + read-only tools: `get_customer_orders`, `get_order_details`, `search_kb` (F-002).
- Happy path works: "where is my order?" → tool call → grounded answer.

**Day 5**
- Conversation persistence, demo-identity auth, event logging on every step.
- ✅ **M2: multi-turn conversation with order lookup, resumable after reload.**

## Phase 2 — Actions & Judgment (Days 6–7)

**Day 6**
- Policy engine (F-003): refund rules as pure functions + tests. Write tools: `initiate_refund`, `update_shipping_address` with policy gate + idempotency.
- Structured `action` SSE events so the UI can show "✓ Refund initiated" cards.

**Day 7**
- Escalation (F-004): triggers (over-limit refund, low retrieval confidence, angry sentiment, explicit "human please"), handoff packet generation (summary, sentiment, attempted actions, suggested next step), escalation queue API.
- ✅ **M3: all three demo flows work — order status, in-policy refund, out-of-policy escalation.**

## Phase 3 — Polish & Proof (Days 8–10)

**Day 8**
- Chat UI polish: streaming, typing indicator, action cards, confirmation prompts for state-changing actions ("Confirm refund of ₹1,499?"), mobile-friendly.

**Day 9**
- Admin dashboard (F-005): metrics tiles, intent breakdown, escalation queue with handoff packets, per-conversation trace view.

**Day 10**
- Eval suite (F-006): 50 scripted scenarios (happy paths, policy edges, prompt injections, out-of-scope requests, rude customers). Runner outputs pass/fail table + summary. Fix failures. **Record the final numbers — they go in the pitch.**

## Phase 4 — Ship (Days 11–12)

**Day 11**
- Deploy backend (Render) + frontend (Vercel). Re-run evals against prod.
- README: problem → demo GIF → architecture diagram → eval results → run instructions.
- Record 2.5-min demo video (assume live demos fail): 20s problem, 90s the three flows, 30s dashboard + eval numbers, 10s close.

**Day 12 — buffer**
- Fix anything broken; dry-run the pitch twice; **submit on the FlowZint portal by mid-day, never the last hour.**

## Cut lines (if behind schedule)

Cut in this order — each cut keeps the demo intact:
1. Warranty-claim tool (refund flow already shows write-actions)
2. Trace view (keep metrics + queue)
3. Sentiment-based escalation (keep rule-based triggers)
4. Eval suite shrinks 50 → 25 scenarios (never cut to zero — it's the differentiator)

**Never cut:** policy engine, escalation, the refund flow, deployment, the video.
