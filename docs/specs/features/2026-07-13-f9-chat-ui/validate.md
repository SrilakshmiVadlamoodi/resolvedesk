# F-009 — Validation Record

## Automated / static checks

- `npm run build` (`tsc -b && vite build`) — **PASS**, no type errors, no build
  errors. Output: `dist/index.html`, `dist/assets/index-*.css` (16.7 kB),
  `dist/assets/index-*.js` (205.8 kB, 64.6 kB gzip).
- `npx oxlint src` — **PASS**, no findings.
- No frontend test suite exists for this feature (no test runner configured in
  `web/package.json` beyond `oxlint`/`tsc`) — verification below is manual/behavioral,
  consistent with F-007's own validate.md treating end-to-end behavior as something
  that needs a live run, not something a type-check substitutes for.

## Manual checks performed in this environment

Ran the real backend locally (`data.seed` + `uvicorn app.main:app`) and hit it
directly to verify assumptions the frontend hardcodes or depends on:

- `POST /auth/demo {"customer_id": 1}` → `customer_id: 1` — confirms
  `demoCustomers.ts`'s `{id: 1, name: "Aditi Rao"}` mapping is correct, not guessed.
- `POST /auth/demo {"customer_id": 2}` → `customer_id: 2` — confirms `{id: 2, name:
  "Rahul Shah"}`.
- `GET /conversations/9999` (nonexistent id) → HTTP 404, `{"detail":"conversation not
  found"}` — confirms `getConversation()`'s `res.status === 404 → return null` branch
  matches the real response shape.
- `POST /chat` with no `ANTHROPIC_API_KEY` configured → **was** a raw `Internal Server
  Error` (500); this has since been fixed in F-007 (see that feature's validate.md) and
  re-verified live: now returns `event: error` / `LLM_UNAVAILABLE` with friendly copy.
  `ErrorNotice.tsx` renders it correctly with no frontend changes needed. This still
  blocks further manual chat-flow verification in this environment, since there's
  simply no real LLM turn happening without a key — but it's no longer a raw crash.

## What is NOT verified yet

This environment has no `ANTHROPIC_API_KEY`, so the actual agent loop cannot run —
every acceptance criterion below that requires a real LLM turn is **unverified by me**
and needs to be checked by the user running `web/` (`npm run dev`) against the local
backend with a real key, per their own instruction not to paste it into chat.

| AC | Status | Notes |
|---|---|---|
| 1. Identity pick → "where's my order?" → typing indicator → streamed answer citing real orders | **NOT VERIFIED** | Needs live LLM call. Code path exists (`applyEvent` on `token`) and the identity ids are confirmed correct (see above). |
| 2. In-policy refund → confirmation card → Confirm → action card with amount/timeline → dashboard reflects it | **PARTIALLY NOT VERIFIED** | Chat-side flow needs a live LLM call. The "dashboard's action count reflects it" half is entirely outside this feature's reach — it depends on F-005's dashboard frontend existing, which per the spec's own "Why this is its own spec" note may not be built yet; not something F-009 can verify regardless of API key availability. |
| 3. Cancel dismisses confirmation, conversation continues | **NOT VERIFIED** | No live-LLM dependency for the cancel path itself (it's local state), but reaching a `confirmation_request` to cancel requires one. |
| 4. Over-limit refund → escalation card with reference; follow-up question still answered | **NOT VERIFIED** | Needs live LLM call (policy engine + escalation packet generation both call the LLM). |
| 5. Mid-conversation reload restores full history + same conversation id; follow-up continues with context | **NOT VERIFIED end-to-end** | The reload/restore mechanics (`getStoredConversationId` + `getConversation`) were exercised against the 404 case only; the "restores a real populated history" case needs an actual conversation to reload, which needs AC1 first. |
| 6. Rate-limit `error` event renders friendly copy | **NOT VERIFIED against live rate limiting** | `ErrorNotice`'s `FRIENDLY_COPY['RATE_LIMITED']` mapping matches F-007's exact `code` value (`RATE_LIMITED`, confirmed by reading `app/api.py` directly), but triggering the real 20/min limit and watching it render wasn't done. |
| 7. Switching demo users starts clean session, previous conversation not visible | **NOT VERIFIED** | `switchUser()` clears all three sessionStorage keys and local state; not exercised against a live second identity in a browser. |
| 8. `npm run build` completes with no errors; built app works against local backend | **PASS (build)**, **NOT VERIFIED (built app against backend)** | Build itself passed (see above). Running `vite preview`'s output against a live backend wasn't done in this pass. |

## Verdict

Build and static checks pass cleanly. The three demo-priority criteria (1, 2, 4) and
the remaining criteria are implemented against F-007's documented contract and
cross-checked where possible without a live LLM call (customer ids, 404 shape,
rate-limit error code), but **require the user to manually verify with a real
`ANTHROPIC_API_KEY`** before this feature can be marked fully done per CLAUDE.md's
definition of done ("works in the deployed environment... appears in the demo script
if demo-relevant"). Two things surfaced during this pass that aren't blockers for
F-009 itself but should be tracked:

1. ~~`POST /chat` returns a raw 500 (not a typed error) when the LLM call itself
   fails~~ — fixed in F-007, re-verified live (see above).
2. `demoCustomers.ts` will silently drift from `data/seed.py` if the seed data changes
   without a matching manual update.
