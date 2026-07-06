# Tech Stack — ResolveDesk

Every choice optimizes for: solo developer, 12 days, free tier, and zero unfamiliar tech.

## Backend

| Concern | Choice | Why |
|---|---|---|
| Language / framework | Python 3.12 + FastAPI | Already fluent; async-native for streaming; automatic OpenAPI docs impress judges for free |
| Data | SQLite + SQLAlchemy 2.0 | Zero-ops, single file, reproducible via `python -m data.seed`; scale story = "swap connection string for Postgres" |
| LLM | Claude API (`claude-sonnet-4-6`) via `app/llm.py` abstraction | Best tool-calling reliability; abstraction layer means Gemini free tier is a 1-file fallback if credits run out |
| Tool calling | Native LLM tool-use API, tools defined as JSON schemas in `app/tools/` | No agent framework (LangChain/CrewAI) — frameworks hide the loop, and the loop *is* the interview story |
| RAG embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`), local | Free, fast, no API dependency; 384-dim vectors fine for a ~40-doc KB |
| Vector store | SQLite table + numpy cosine similarity | At KB scale (< 500 chunks) brute force is < 5 ms; adding a vector DB would be resume-driven overengineering |
| Conversation state | `conversations` + `messages` tables | Server-side history; conversation resumes across page reloads |
| Event log | Append-only `events` table (tool calls, escalations, policy decisions) | Single source of truth for dashboard + debugging + demo traces |

## Frontend

| Concern | Choice | Why |
|---|---|---|
| Framework | React + Vite | Already known; fast dev loop |
| Styling | Tailwind CSS | Speed; consistent look without a designer |
| Chat streaming | SSE (Server-Sent Events) from FastAPI | Simpler than WebSockets, one-directional is all chat needs; typing indicators feel premium |
| Charts (dashboard) | Recharts | Small API surface, looks clean out of the box |

## Infra & tooling

| Concern | Choice | Why |
|---|---|---|
| Backend hosting | Render free tier (Docker) | Free, supports background processes; cold starts are acceptable (mitigated by a pinger before demo) |
| Frontend hosting | Vercel | Free, instant deploys, judges get a clickable link |
| Dev workflow | Claude Code + this SDD package, project at `C:\dev\resolvedesk` | Known-good Windows setup (avoids the OneDrive/uv hardlink issue) |
| Package mgmt | `uv` for Python, `npm` for web | Fast installs |
| Testing | `pytest` for unit tests; custom eval runner in `evals/` | Eval suite is a first-class feature, not an afterthought |
| CI | GitHub Actions: lint + pytest + eval smoke subset on push | Green checkmarks on a public repo signal professionalism |

## Key architectural rules

1. **The agent loop is hand-written** (`app/agent.py`): build messages → call LLM → if tool_use, validate against policy → execute → append result → repeat (max 6 iterations) → final answer. ~150 lines, fully explainable in an interview.
2. **Policy is code, not prompt** (`app/policy.py`): pure functions like `can_auto_refund(order, amount) -> PolicyDecision`. Prompts can be injected; Python functions can't.
3. **Provider-agnostic LLM layer** (`app/llm.py`): one `complete(messages, tools) -> LLMResponse` function. Swapping Claude ↔ Gemini touches one file.
4. **Everything observable**: every tool call, policy decision, retrieval, and escalation emits an event. The dashboard is a pure read model over events.
