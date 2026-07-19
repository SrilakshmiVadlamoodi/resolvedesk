# F-008 — Implementation Notes

## What was built

- **`app/config.py`** — added `llm_provider: str = "gemini"` (env `LLM_PROVIDER`) and
  `gemini_api_key: str = ""` (env `GEMINI_API_KEY`), alongside the existing
  `anthropic_api_key`.
- **`app/llm.py`** — added `_to_gemini_contents()`, `_gemini_tool_declarations()`,
  `_generate_gemini_content()` (retry-wrapped), and `_complete_gemini()`. The old
  `complete()` body was renamed to `_complete_anthropic()` unchanged; `complete()` is
  now a two-line dispatcher on `settings.llm_provider`.
- Added `google-genai` as a dependency (`uv add google-genai`) — its transitive
  `tenacity` dependency is reused for the 429 retry/backoff rather than hand-rolling one.

## Key decisions

- **Tool-call id recovery for `function_response`.** Gemini requires the function
  *name* on a `function_response` part; our `tool` messages only carry
  `tool_call_id` (F-002's format, unchanged to avoid touching `app/agent.py`).
  `_to_gemini_contents` tracks `call_id -> name` from the preceding assistant
  `tool_calls` while converting, so nothing upstream had to change.
- **Retry only on 429, not all `APIError`s.** A 500 or malformed-request error retried
  the same way as a rate limit would mask real bugs as transient failures; `tenacity`'s
  `retry_if_exception` predicate checks `exc.code == 429` specifically.
- **`_generate_gemini_content` is a separate, thin function** (client + kwargs in,
  response out) purely so retry tests can call it directly with a mocked client instead
  of monkeypatching the whole `genai.Client` construction inside `_complete_gemini`.

## Deviations from spec
None.

## Follow-ups (not blocking F-008)
- AC5 (real eval pass rate against live Gemini) could not be executed in this
  environment — no `GEMINI_API_KEY` present. See `validate.md` for the exact command to
  run.
