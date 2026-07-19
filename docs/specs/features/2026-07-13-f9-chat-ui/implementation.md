# F-009 — Implementation Notes

## What was built

- **`web/src/api.ts`** — the single module owning all fetch/SSE traffic with the
  backend (spec's `api.js`, adapted to `.ts` since the project is TypeScript, not
  JS — see Deviations). Session token + customer id/name in sessionStorage (mirrored
  in a module-level variable), `authDemo`, `switchUser`, `sendMessage`, `confirmAction`,
  `getConversation`. SSE parsing (`readSSE`) reads the `fetch` response body via
  `ReadableStream.getReader()`, buffers on `\n\n` frame boundaries, and extracts
  `event:`/`data:` lines — not `EventSource`, since the chat POST needs a body.
- **`web/src/types.ts`** — a `ChatItem` discriminated union (`user` / `assistant` /
  `action` / `confirmation` / `escalation` / `error`) that the message list renders
  from. One flat list, not separate per-type arrays, so ordering in the conversation is
  trivially correct.
- **`web/src/hooks/useTypewriter.ts`** — client-side character-reveal animation over
  an already-fully-received string. See Deviations — this exists because F-007 does
  not stream incrementally.
- **`web/src/demoCustomers.ts`** — hardcoded `{id, name, orderCount}` for the 2 seeded
  demo customers, read from `data/seed.py`. See Deviations — there is no API to
  discover this list.
- **Components** (`web/src/components/`): `IdentityPicker`, `ChatHeader`,
  `MessageList` (auto-scroll + "jump to latest" pill, scroll-position tracked via a
  ref and an 80px near-bottom threshold), `MessageBubble`, `TypingIndicator`,
  `ActionCard` (refund/address/warranty), `ConfirmationCard` (pending → confirmed /
  cancelled / error states), `EscalationCard`, `ErrorNotice` (rate-limit-specific
  copy), `ChatInput` (Enter-to-send, Shift+Enter for newline).
- **`web/src/App.tsx`** — orchestrator. Owns `session`, `conversationId`, `items`
  (the `ChatItem[]`), and the pending-confirmation-derived `inputDisabled` flag.
  Resumes an existing session + conversation on mount via `getConversation()`. All SSE
  event handling (`conversation` / `token` / `action` / `confirmation_request` /
  `escalated` / `error` / `done`) funnels through one `applyEvent()` function shared by
  both `handleSend` and `handleConfirm`, so the two entry points can't drift in how
  they interpret the same event vocabulary.
- **`web/src/index.css`** — Tailwind v4 `@theme` tokens for the chosen visual
  direction: warm off-white surface (`--color-surface: #faf9f6`), deep teal accent
  (`--color-brand: #0f6b5c`), muted success/amber/danger tints for action/escalation/
  error cards. Deliberately not the generic purple-gradient-on-white "AI slop" default,
  and not a literal `Inter` font stack — system sans (`Segoe UI`/`-apple-system`/...).
- **`web/src/vite-env.d.ts`** — types `import.meta.env.VITE_API_BASE_URL` explicitly
  (Vite's default `ImportMetaEnv` doesn't know app-specific env vars).
- **`web/.env.example`** — `VITE_API_BASE_URL=http://localhost:8000`.

## Key decisions

- **Client-side typewriter instead of real token streaming.** `app/api.py`'s
  `_turn_result_to_sse` calls `agent.run_turn()` synchronously and emits exactly one
  `token` event containing the complete final answer — there is no incremental
  generation happening server-side to forward. This was flagged to the user before
  writing any components, since the spec explicitly requires "text appears
  progressively." Per the user's explicit choice, `useTypewriter` animates the
  already-complete text a few characters per tick after it arrives, so the demo
  recording still reads as a live response. This is cosmetic, not real streaming, and
  is documented as such in the hook's own doc comment so it isn't mistaken for one
  later.
- **Hardcoded demo customer list.** `POST /auth/demo` accepts a `customer_id` but there
  is no endpoint to discover customer names — the picker has nothing to call. Also,
  only 2 customers are seeded (Aditi Rao, Rahul Shah), not the 3–4 the spec assumed.
  `demoCustomers.ts` hardcodes `{id: 1, name: "Aditi Rao", orderCount: 2}` and
  `{id: 2, name: "Rahul Shah", orderCount: 1}`, sourced from `data/seed.py`'s
  insertion order and order counts, and verified against a live `POST /auth/demo` call
  (`customer_id: 1` → Aditi, `customer_id: 2` → Rahul — confirmed, not assumed). This
  is fragile to `data/seed.py` changing without this file being updated in step; flagged
  as a follow-up.
- **`api.js` → `api.ts`.** The spec names `web/src/api.js`, but `web/` is a TypeScript
  project (`tsc -b` gates the build, `verbatimModuleSyntax` on). Writing plain JS into
  a TS project would either need `allowJs` (not configured) or silently bypass type
  checking for the one file that owns every network contract with the backend — the
  highest-value file to have typed. Treated as a naming detail, not a stack change.
- **No "frontend-design" skill was available in this environment** (only
  `artifact-design`, which targets published Artifacts, not a real React app). Applied
  the same underlying principles by hand: one deliberate palette (see `index.css`
  above), avoided the generic AI-slop defaults (purple gradients, literal `Inter`,
  predictable card-in-a-box layout with no hierarchy), real spacing scale via
  Tailwind's default scale rather than ad hoc pixel values.
- **`ChatItem[]` is a flat append-only list per conversation turn**, not a nested
  `{message, actions[], confirmation?}` structure. Every SSE event becomes exactly one
  new item (or, for `error`/`confirmation_request`, updates one existing item's status
  in place). This matches the fact that a single turn can legitimately produce multiple
  visible things (e.g. an assistant message *and* an action card), and keeps
  `MessageList` a single `.map()` over one array.
- **One shared `applyEvent()` for both `/chat` and `/chat/confirm` responses.** Both
  endpoints emit the same typed SSE vocabulary (`_turn_result_to_sse` is the single
  producer on the backend side for both), so handling them via two separate switch
  statements risked the confirm path silently missing a case the send path handles
  (or vice versa) if the event vocabulary changes later.

## A backend behavior discovered, and since fixed (F-007)

While manually exercising the local backend (no `ANTHROPIC_API_KEY` available in this
environment — see validate.md), `POST /chat` with no LLM key configured returned a raw
`Internal Server Error` (HTTP 500), not a typed `error` SSE event. Flagged to the user
in the same turn it was found rather than worked around in the frontend. **Fixed as a
follow-up F-007 change** (see that feature's implementation.md, "Post-hoc fix" section)
— `app/agent.py`'s LLM call site now catches provider/network exceptions and returns
`TurnResult(error="LLM_UNAVAILABLE", ...)`, which surfaces as a normal typed `error` SSE
event. `ErrorNotice.tsx` already handles any `code` it doesn't have specific copy for by
falling back to the event's `message` field, so this required zero frontend changes —
confirmed live: `POST /chat` with no key now returns `event: error` /
`LLM_UNAVAILABLE` / the friendly copy, not a 500.

## Deviations from spec

- `api.js` → `api.ts` (naming only — see above).
- Cosmetic typewriter instead of real incremental SSE streaming — see above,
  user-approved before implementation.
- Demo customer list hardcoded client-side rather than fetched — see above, no
  backend endpoint exists to fetch it, and backend is frozen for this spec.
- "frontend-design skill" guidance was not literally available; applied the underlying
  principles manually — see above.

## Follow-ups (not blocking F-009)

- If `data/seed.py`'s demo customers ever change, `web/src/demoCustomers.ts` must be
  updated by hand — nothing enforces they stay in sync.
- The F-007 500-on-LLM-failure gap above should probably become its own small F-007
  follow-up spec (catch the exception, emit a typed `error` event) before the real
  demo, since a transient Anthropic API hiccup during a live recording would currently
  render as a blank failed request rather than the friendly error copy this feature
  already knows how to show.
- Real token-by-token streaming (switching `app/llm.py` to Anthropic's streaming API)
  would let this feature's typewriter be driven by genuine incremental `token` events
  instead of a single complete string — no frontend changes needed beyond removing the
  "cosmetic" framing, since `useTypewriter`/`MessageBubble` already consume `text`
  generically.
