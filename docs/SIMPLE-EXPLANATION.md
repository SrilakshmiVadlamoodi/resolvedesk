# ResolveDesk, Explained Simply

*A no-jargon walkthrough of everything in this package. Share this with anyone — a judge, a teammate, your sister.*

## The idea in one paragraph

Imagine an online electronics store. When your parcel is late or a product is broken, you usually chat with a bot that can only recite FAQs, and then you wait hours for a human anyway. ResolveDesk is a support agent that can actually *do* things: it checks your real order, and if the rules allow it, it refunds your money right there in the chat. If the rules don't allow it, it doesn't argue or guess — it writes a neat summary and passes you to a human, so you never have to repeat your story.

## The restaurant analogy (how the whole system works)

Think of a restaurant:

- **The waiter (the AI agent)** talks to you politely and figures out what you want. But the waiter doesn't cook and doesn't handle the cash register.
- **The recipe book (the knowledge base / RAG)** — when you ask "is this dish spicy?", the waiter doesn't guess; they check the book. If the book doesn't say, the waiter admits it instead of making something up. "RAG" just means: *look it up first, then answer.*
- **The kitchen (the tools)** — when you order, the waiter passes a written slip to the kitchen: "Table 4, one refund, order VK-1042." The kitchen only accepts properly-filled slips. That's "tool calling": the AI fills in a form, and normal reliable code does the actual work.
- **The manager's rulebook (the policy engine)** — the waiter is allowed to comp a dessert, but not to give a free ₹8,000 dinner. Those limits are written in the rulebook, and the rulebook is enforced by the *register*, not by trusting the waiter. In our system the rules are real Python code — so even if a clever customer sweet-talks the waiter ("your manager already approved it!"), the register still says no.
- **Calling the manager (escalation)** — when something is above the waiter's authority, they fetch the manager AND brief them: "Table 4, broken laptop stand, delivered 4 days ago, wants ₹8,499, everything checks out except the amount." The manager can decide in ten seconds. That briefing is our "handoff packet."
- **The CCTV and receipts (the event log)** — everything that happens is written down: every lookup, every refund, every rule decision. Nothing relies on anyone's memory.
- **The owner's office screen (the dashboard)** — the owner doesn't watch every table; they watch a screen: how many customers were served without a manager, what people ask about most, how much was refunded today. Our dashboard is exactly that, built entirely from the receipts.
- **The health inspection (the eval suite)** — before opening, we run 50 rehearsals: normal customers, confused customers, rude customers, and con artists trying to trick the waiter. We record the score. Telling judges "it passed 90% of 50 rehearsals, including trick attempts" is far more convincing than "trust me, it works."

## What each file in this package is for

- **CLAUDE.md (the constitution)** — the house rules for the AI coding assistant building this. Like a team lead's standing instructions: "always check the spec first, never let the AI touch money directly, don't add features we didn't plan."
- **mission.md** — *why* we're building this and what success looks like. Keeps every decision pointed at making the demo convincing.
- **tech-stack.md** — the shopping list of technologies, each with a one-line reason. The theme: boring, free, already-known tools everywhere except the one place we want to shine (the agent itself).
- **architecture.md** — the floor plan. How a message travels: chat → agent → rulebook → kitchen → database → back to you. Also the safety locks (a customer can only ever see their *own* orders — enforced by the server, not by trusting the AI).
- **roadmap.md** — the 12-day calendar. Days 1–2 build the foundations, 3–5 make it talk and look things up, 6–7 give it hands (refunds) and judgment (escalation), 8–10 make it pretty and prove it works, 11–12 put it on the internet, film it, and submit early. It also lists what to cut first if time runs short — deciding that *now* beats panicking on day 10.
- **features/001–006** — one contract per feature: what it does, how we'll know it's done ("acceptance criteria"), and what we're deliberately *not* doing. When you tell Claude Code "build feature 003," this is what it reads.

## What makes this different

Most solo hackathon entries are the recipe-book-only waiter: they can answer questions but can't act. This one takes actions, has hard-coded limits a jailbreak can't cross, hands off to humans gracefully, shows the business a live dashboard, and comes with test scores. Each of those is one sentence in a pitch — together they sound like a product built by a team, shipped by one person in 12 days.
