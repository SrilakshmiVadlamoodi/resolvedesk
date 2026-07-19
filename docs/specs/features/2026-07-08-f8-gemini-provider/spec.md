# F-008 — Gemini as Primary LLM Provider

## Goal
Make Gemini the default, submission-time LLM provider (not just a dev/cost fallback),
while keeping the existing Anthropic implementation fully intact and selectable — the
tech-stack spec always described the provider abstraction as a 1-file swap; this
exercises that promise for real.

## Scope decision
Not on the original roadmap (`docs/specs/roadmap.md`) — added by explicit user decision
to change the submission's primary provider. Kept deliberately small: one new provider
branch in `app/llm.py`, a config default flip, docs updates. No new tools, no changes to
`app/agent.py`'s call contract (`complete(messages, tools) -> LLMResponse`).

## Interface (unchanged contract, new branch)
```python
def complete(messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
    ...  # dispatches on settings.llm_provider: "anthropic" | "gemini"
```
- `app/config.py` gains `llm_provider: str = "gemini"` (env `LLM_PROVIDER`) and
  `gemini_api_key: str = ""` (env `GEMINI_API_KEY`), alongside the existing
  `anthropic_api_key`.
- `app/llm.py` gains `_to_gemini_contents()` (mirrors `_to_anthropic_messages`) and a
  `_complete_gemini()` path, selected by `complete()` based on `settings.llm_provider`.
  `_complete_anthropic()` is the existing logic, renamed but behaviorally identical.
- Gemini 429s get retried with exponential backoff (bounded attempts) before surfacing
  an error, since the live demo now depends on this path.

## Acceptance criteria
1. `settings.llm_provider` defaults to `"gemini"`; setting `LLM_PROVIDER=anthropic`
   selects the untouched Anthropic path.
2. `_to_gemini_contents()` converts our provider-agnostic message list (system/user/
   assistant-with-tool_calls/tool-result) into Gemini's `contents` + `system_instruction`
   shape, unit-tested the same way `_to_anthropic_messages` is.
3. Gemini tool-call responses (`function_call` parts) map into `LLMResponse.tool_calls`
   with the same `{id, name, arguments}` shape the agent loop already expects, so
   `app/agent.py` needs zero changes.
4. A 429 from the Gemini SDK triggers up to 3 retries with exponential backoff
   (base delay, doubling, jitter optional); after exhausting retries the error
   propagates as a typed failure rather than crashing the process — matches F-007's
   existing "typed error, not a dropped connection" convention for the chat API.
5. Full eval suite (`evals/run.py`, no `--subset smoke`) runs against
   `LLM_PROVIDER=gemini` and the resulting pass rate is recorded in this feature's
   `validate.md` — **requires a real `GEMINI_API_KEY`, cannot be produced by unit tests
   alone.**

## Out of scope
- Streaming Gemini responses token-by-token (matches F-007's existing simplification for
  Anthropic).
- Removing or deprecating the Anthropic path — stays fully supported per explicit
  request.
- Changing eval scenario content to be "Gemini-friendly" — scenario failures caused by
  genuine Gemini behavior differences (tool-calling conventions, refusal patterns) are
  reported, not papered over.
