# F-008 — Validation Record

## Automated tests

`uv run pytest -q` — 147/147 passed (all prior tests + 7 new: 4 message-conversion,
3 retry/backoff).
`uv run ruff check app tests` — all checks passed.

| File | Covers |
|---|---|
| `tests/test_llm_gemini_message_conversion.py` | system/user/assistant-tool_call/tool-result → Gemini `contents` shape (AC2, AC3) |
| `tests/test_llm_gemini_retry.py` | 429 retried up to 3 attempts then succeeds; gives up and reraises after exhausting retries; non-429 errors are not retried (AC4) |
| `tests/test_llm_message_conversion.py` (unchanged) | proves the Anthropic path is untouched (AC1) |

## Acceptance criteria (from spec.md)

**1. `settings.llm_provider` defaults to `"gemini"`; `LLM_PROVIDER=anthropic` selects the untouched Anthropic path.**
PASS — `app/config.py` default is `"gemini"`; `complete()` dispatches on
`settings.llm_provider`; `_complete_anthropic` is the original, unmodified logic.

**2/3. Gemini message and tool-call conversion matches the shape `app/agent.py` expects.**
PASS — see `test_llm_gemini_message_conversion.py`. `_complete_gemini` maps Gemini
`function_call` parts back into `{id, name, arguments}`, so `app/agent.py` required zero
changes.

**4. 429 triggers bounded exponential-backoff retry; exhausted retries surface a typed error, not a crash.**
PASS — `_generate_gemini_content` is wrapped in `tenacity.retry` (max 3 attempts,
random exponential wait, only on `APIError.code == 429`); after exhausting retries the
original `genai_errors.APIError` propagates up through `complete()` the same way any
other LLM failure would (F-007's chat endpoint already turns `complete()` exceptions
into a typed SSE `error` event — no new handling needed there).

**5. Full eval suite run against `LLM_PROVIDER=gemini`, real pass rate recorded.**
**NOT RUN — no `GEMINI_API_KEY` available in this environment** (no `.env` file, no env
var set). Unit tests above confirm the provider's message/tool-call plumbing and retry
behavior are correct, but cannot substitute for an end-to-end pass rate against the live
API. **Action required:** run
`GEMINI_API_KEY=<key> LLM_PROVIDER=gemini uv run python -m evals.run` (no `--subset
smoke`) with a real key and record the result here before citing a number in the
submission.

## Out-of-scope check
No token-by-token Gemini streaming, no removal of the Anthropic path, no eval scenario
content changes — matches spec.

## Verdict
4/5 acceptance criteria PASS by automated test. AC5 (real pass rate) is blocked on a
`GEMINI_API_KEY` this environment doesn't have — must be run by the user before the
number goes in the pitch.

## Post-validation note (real key, later testing)

Gemini was subsequently tested with a real key. Two findings changed the plan:

- **Quota.** The available key's free-tier quota was far lower than the commonly cited
  figure — observed ~20 requests/day, vs. the ~1,500/day typically documented for
  `gemini-2.5-flash` free tier. Whatever the cause (account tier, regional variation,
  quota changes since documented), it's not enough to run the full eval suite, let alone
  iterate on it.
- **Behavior.** Independent of quota, several scenarios surfaced a genuine behavioral
  difference rather than a bug: Gemini favored asking a clarifying question over making
  the autonomous tool call the scenario was designed around, in `escalation-05`,
  `escalation-06`, `happy-02`, and `happy-12`. Claude's tool-use pattern on these same
  scenarios is more decisive — it acts on the available context instead of pausing to
  ask. This isn't necessarily "wrong" behavior for Gemini, but it doesn't match what the
  scenarios were built to test, and reconciling it would mean rewriting scenarios around
  Gemini's style rather than evaluating the agent design itself.

**Conclusion:** Claude Haiku 4.5 (`LLM_PROVIDER=anthropic`, the default) is used for the
real submission and eval numbers. Gemini remains available via `LLM_PROVIDER=gemini` for
cheap local dev-time sanity checks only — not relied on for reported pass rates.
