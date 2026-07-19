# Mission — ResolveDesk

## One-liner

An AI support agent that *resolves* tickets, not just answers questions — grounded in a knowledge base, empowered with real tools, constrained by explicit policy, and honest about when to hand off to a human.

## The problem

Customer support for D2C e-commerce is expensive and slow. Industry-typical numbers: 60–80% of inbound tickets are repetitive (order status, refund requests, address changes, warranty questions), median first-response times run in hours, and human agents cost real money per resolved ticket. Existing "AI chatbots" mostly deflect — they answer FAQs but can't *do* anything, so the customer ends up waiting for a human anyway. Deflection without resolution just adds a frustrating extra step.

## The solution

ResolveDesk is an agentic support system for VoltKart, a fictional D2C electronics store. It:

1. **Answers** product and policy questions from a versioned knowledge base (RAG).
2. **Acts** — looks up orders, initiates refunds within policy limits, updates shipping addresses, files warranty claims — via typed tool calls against the store backend.
3. **Escalates** — when the request exceeds its authority, retrieval confidence is low, or the customer is angry — handing the human agent a structured summary: what the customer wants, what the agent already tried, sentiment, and suggested next step.
4. **Reports** — an admin dashboard showing resolution rate, escalation reasons, top intents, and per-conversation traces, built from a full event log.

## Who it's for

- **Primary (demo persona):** VoltKart customers with post-purchase issues.
- **Secondary (business persona):** VoltKart support leads who monitor the dashboard and work the escalation queue.
- **Actual audience:** FlowZint judges evaluating innovation, real-world problem solving, AI automation, UX, and scalability.

## What success looks like

The agent visibly *does things* (a refund appears in the mock backend live) and we show eval numbers (≥ 90% pass rate on a 50-scenario suite) as evidence of engineering rigor.

## Explicit non-goals

- No real payments, real user accounts, or real customer data — everything is seeded mock data.
- No multi-tenant support; one store, one KB.
- No voice, no WhatsApp/Slack channels — web chat only.
- No fine-tuning; prompt + tools + retrieval only.
- No human-agent chat UI — the escalation queue shows handoff packets, it doesn't implement the human side of the conversation.

## Guiding principle

Every design decision is judged by one question: *does this make the 3-minute demo more convincing?* If not, it's backlog.
