# Deployment — Render (backend)

**Status: deferred for this submission.** A live URL is optional per the FlowZint
hackathon rules, and the submission demo runs locally instead (`uv run uvicorn` +
`npm run dev`), recorded in the demo video. Everything below is kept as the known
next step if a public deploy is needed later — it has not been re-verified against
the current default provider (`openrouter`, see `README.md`) and should be reviewed
before actually deploying.

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes (primary)** | Required since `LLM_PROVIDER` defaults to `anthropic`. Live demo and judged submission run on Claude Haiku 4.5 (`app/llm.py`). |
| `LLM_PROVIDER` | No | Defaults to `anthropic`. Set to `gemini` only for optional free-tier dev-time sanity checks — see the Gemini caveat in `README.md`. Not used for real eval numbers. |
| `GEMINI_API_KEY` | Optional | Only needed if `LLM_PROVIDER=gemini` is set. |
| `DATABASE_URL` | No | Defaults to local SQLite file; fine for hackathon-scale demo. |
| `SESSION_SECRET` | Yes | Used to sign demo identity tokens (`app/auth.py`). |
| `ALLOWED_ORIGINS` | **Yes** | Comma-separated CORS allowlist (`app/main.py`). Defaults to `http://localhost:5173` (Vite dev server) — **must be set to the real Vercel URL on Render**, or the deployed frontend will fail every request with a CORS error, same as the localhost issue this fixed. |

## Build / start

```bash
uv sync --no-dev
uv run python -m data.seed
uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Post-deploy checklist

- [ ] Re-run the eval suite against the deployed URL (`docs/specs/roadmap.md` Day 11).
- [ ] Confirm `ANTHROPIC_API_KEY` is set in Render's environment (not just locally) —
      without it, `LLM_PROVIDER=anthropic`'s default path will fail on first request.
- [ ] Set `ALLOWED_ORIGINS` in Render's environment to the actual Vercel domain (e.g.
      `https://resolvedesk.vercel.app`) — the `http://localhost:5173` default only
      works for local dev and will silently block the deployed frontend otherwise.
- [ ] Confirm rate-limit retry/backoff (F-008) doesn't push response latency past what's
      acceptable for the live demo — a judge triggering several rapid requests should
      degrade gracefully, not stall.
