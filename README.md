# ResolveDesk

An agentic customer-support platform for VoltKart, a fictional D2C electronics store —
built for FlowZint AI Hackathon 2026 (Support Chat Bot category). It answers from a
knowledge base, takes real actions (order lookup, refunds, address changes) via tool
calls bounded by a policy engine, and escalates to a human with full context when it
can't or shouldn't act on its own. See `docs/specs/mission.md` for the full pitch.

**No live URL for this submission** — a public deploy is optional per the FlowZint
rules, so this runs locally only; the submitted demo video shows it running via the
commands below. See `docs/specs/deployment.md` for the deferred Render/Vercel plan.

## LLM provider

**OpenRouter (Claude Haiku 4.5) is the default and primary provider** — used for the
eval suite, the live demo, and the final submission. It's reached via OpenRouter's
OpenAI-compatible `chat.completions` API (`base_url=https://openrouter.ai/api/v1`,
model `anthropic/claude-haiku-4.5`), so no extra SDK is required beyond the `openai`
client already used by this project's tooling. Direct Anthropic access, Together AI
(Llama 3.3 70B Instruct Turbo), GitHub Models (GPT-4.1), and Gemini remain fully
implemented and selectable for dev-time comparison — the provider abstraction lives
entirely in `app/llm.py`, so switching is one environment variable:

```bash
LLM_PROVIDER=openrouter  # default — Claude Haiku 4.5 via OpenRouter, used for real eval numbers/submission
LLM_PROVIDER=anthropic   # optional — Claude Haiku 4.5 via direct Anthropic API
LLM_PROVIDER=together    # optional — Llama 3.3 70B Instruct Turbo via Together AI
LLM_PROVIDER=github      # optional — GPT-4.1 via GitHub Models
LLM_PROVIDER=gemini      # optional — cheap local sanity checks only, see caveat below
```

Set the corresponding API key:

- `OPENROUTER_API_KEY` — required (default provider)
- `ANTHROPIC_API_KEY` — only needed if you set `LLM_PROVIDER=anthropic`
- `TOGETHER_API_KEY` — only needed if you set `LLM_PROVIDER=together`
- `GITHUB_MODELS_TOKEN` — only needed if you set `LLM_PROVIDER=github`; a GitHub PAT
  with the `models` scope
- `GEMINI_API_KEY` — only needed if you set `LLM_PROVIDER=gemini`

Cerebras (Gemma 4 31B) was evaluated and removed: it called tools correctly in
single-step flows, but in multi-step refund flows (`happy-06-in-policy-refund`,
`policy-01-over-limit`) it sometimes explained the outcome in prose instead of calling
`initiate_refund`, which skips the policy engine entirely — a correctness failure, not
just a lower pass rate.

**Gemini caveat:** it is not used for real eval numbers or the submission. Testing found
two problems: its tool-calling behavior is more conservative than Claude's — in several
scenarios (`escalation-05`, `escalation-06`, `happy-02`, `happy-12`) it asked a
clarifying question instead of calling a tool the way the scenario was designed around;
and the free-tier quota on the key used for testing was far lower than documented
(~20 requests/day observed vs. the commonly cited ~1,500/day), which alone rules it out
for a full eval run. See
`docs/specs/features/2026-07-08-f8-gemini-provider/validate.md` for details.

## Running locally

Backend:

```bash
uv sync
cp .env.example .env   # fill in OPENROUTER_API_KEY
uv run python -m data.seed
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

Frontend (separate terminal):

```bash
cd web
npm install
cp .env.example .env   # VITE_API_BASE_URL defaults to http://localhost:8000
npm run dev             # http://localhost:5173
```

Open `http://localhost:5173` — the frontend talks to the backend at
`VITE_API_BASE_URL`, and the backend's `ALLOWED_ORIGINS` (`.env`, defaults to
`http://localhost:5173`) must include wherever the frontend is actually running.

## Tests and evals

```bash
uv run pytest
uv run ruff check app data tests
uv run python -m evals.run              # full eval suite against the configured provider
uv run python -m evals.run --subset smoke
```

Eval pass rate is recorded per-provider in the relevant feature's `validate.md` under
`docs/specs/features/`.

## Eval results and a real tradeoff

The default provider (Claude Haiku 4.5 via OpenRouter) scores **67.3% (35/52)** on the
full eval suite — below the 90% target. The gap is a known, diagnosed model behavior
(Haiku sometimes explains an outcome in prose or asks a clarifying question instead of
calling the required tool, even when instructed to call it first), not a hidden bug —
see `docs/specs/features/2026-07-19-f10-openrouter-haiku-provider/validate.md` for the
full root-cause writeup and the two mitigations attempted. We assess Claude Sonnet 4.6
would likely score higher here, but didn't switch for submission: remaining API budget
($3.87) covered at most one full Sonnet eval run with no margin for a retry or live
demo traffic, so we kept the known-working, fully-tested Haiku setup instead.

## Project structure

- `app/` — backend (FastAPI, agent loop, policy engine, tools)
- `web/` — frontend
- `evals/` — scripted eval suite
- `data/` — seed data and DB schema
- `docs/specs/` — mission, roadmap, architecture, and per-feature specs (spec-first,
  see `CLAUDE.md`)
