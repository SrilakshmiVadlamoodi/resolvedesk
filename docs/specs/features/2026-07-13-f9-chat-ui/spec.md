# F-009 — Chat UI Implementation

## Why this is its own spec
F-007 built and tested the chat API surface (SSE streaming, persistence, confirmation flow), but no frontend consumes it — the web app currently renders only the Vite starter heading. This spec owns the customer-facing chat interface. The admin dashboard UI belongs to F-005 and is not in scope here; if F-005's frontend views also don't exist yet, complete them separately against F-005's spec.

## Goal
A polished, demo-ready chat interface where a VoltKart customer can converse with the agent, see actions happen (refunds, address changes) as visible cards, confirm write actions explicitly, and understand escalations — consuming F-007's endpoints exactly as specified, with no backend changes.

## Screens & components

### 1. Identity picker (entry screen)
- On first load, call `POST /auth/demo` flow: show a simple card listing 3–4 seeded demo customers by name ("Sign in as Priya — 3 orders", etc.).
- Selecting one stores the session token (in-memory + sessionStorage so a reload keeps the session) and enters the chat.
- Small persistent badge in the header showing who you're signed in as, with a "switch user" action (useful for the demo: switch customers to show order scoping).

### 2. Chat screen (the core)
Layout: header (VoltKart branding + signed-in badge), scrollable message list, input bar pinned at bottom.

**Message list**
- User messages right-aligned, agent messages left-aligned, timestamps subtle.
- Agent responses stream token-by-token from the SSE `token` events — text appears progressively, with a typing indicator shown between sending a message and the first token arriving.
- Auto-scroll to bottom on new content, but if the user has scrolled up, show a "jump to latest" pill instead of yanking them down.

**Action cards** (rendered inline in the conversation when an `action` SSE event arrives)
- `refund_initiated`: card with a check icon, "Refund of ₹1,499 initiated", order id, and "5–7 business days" timeline.
- `address_updated`: card with the new address summary.
- Cards are visually distinct from chat bubbles (bordered card, accent color) — these are the money shot of the demo; they must be instantly legible in a screen recording.

**Confirmation dialog** (on `confirmation_request` SSE event)
- Modal or inline card: "Confirm refund of ₹1,499 for order VK-1042?" with Confirm / Cancel buttons.
- Confirm → `POST /chat/confirm` with the nonce; then render the resulting `action` or `error` event.
- Cancel → dismiss locally and send nothing; the input bar is re-enabled so the customer can continue.
- While a confirmation is pending, disable the input bar (matches F-007's single-pending-action model; the backend's nonce expiry is the source of truth, so if the user waits >5 min and then confirms, render the typed error gracefully).

**Escalation display** (on `escalated` SSE event)
- Distinct card (amber/handoff styling): "This has been raised with our support team — reference #E-107, expect a response within 4 business hours."
- Conversation remains usable afterward (F-007 guarantees the agent still answers unrelated questions).

**Errors** (on `error` SSE event)
- Friendly inline notice, never a raw stack trace. Rate-limit errors get specific copy: "You're sending messages quickly — give it a few seconds."

### 3. Conversation persistence behavior
- On load with an existing session: fetch `GET /conversations/{id}` (id kept in sessionStorage) and render full history, so a page reload mid-conversation visibly resumes — this is demo-relevant (it proves F-007's persistence claim on camera).
- "New conversation" button in the header clears the stored id and starts fresh.

## Technical requirements
- React + Vite + Tailwind (existing stack). Components in `web/src/components/`, API client in `web/src/api.js` — one module owning fetch/SSE logic so endpoints aren't scattered.
- SSE consumption via `fetch` + `ReadableStream` reader (not `EventSource`, since the chat POST needs a body). Parse the typed events (`token`, `action`, `confirmation_request`, `escalated`, `done`, `error`) exactly as F-007 defines them.
- API base URL from `import.meta.env.VITE_API_BASE_URL` with `http://localhost:8000` as dev default — this is what flips to the Render URL at deploy time.
- No new backend endpoints, no backend changes. If the UI seems to need something the API doesn't provide, stop and flag it — that's an F-007 spec conversation, not a quiet workaround.
- Visual design follows the frontend-design skill guidance: pick one deliberate aesthetic direction (clean, warm, trustworthy commerce support — not a generic gray bot widget), consistent spacing, real typographic hierarchy. Must look intentional in a full-screen recording at 1080p.
- Mobile-responsive enough to not embarrass (single column collapses cleanly), but desktop is the demo target — do not spend polish hours on mobile.

## Acceptance criteria
1. Fresh load → pick a demo identity → send "where's my order?" → typing indicator → streamed answer citing that customer's real seeded orders.
2. In-policy refund request → confirmation card appears → Confirm → action card renders with amount and timeline → dashboard's action count (F-005 API) reflects it on next poll.
3. Cancel on a confirmation dismisses it and the conversation continues normally.
4. Over-limit refund → escalation card with reference id renders; a follow-up unrelated question still gets a normal answer in the same thread.
5. Mid-conversation page reload restores the full visible history and the same conversation id; sending another message continues with context.
6. Rate-limit `error` event renders the friendly copy, not a crash or blank bubble.
7. Switching demo users starts a clean session; the previous user's conversation is not visible to the new one.
8. `npm run build` completes with no errors; the built app works against the local backend (not just the dev server).

## Out of scope
Admin dashboard views (F-005), auth beyond the demo picker, message editing/deletion, file uploads, dark mode, i18n, mobile-first polish, typing indicators for the "human agent" side (no human side exists — F-004).

## Demo alignment note
The three recorded demo flows map to acceptance criteria 1, 2, and 4. Those three paths get the most visual polish; anything else gets functional-but-plain treatment. When in doubt where to spend an hour, spend it on how criteria 1/2/4 look on camera.
