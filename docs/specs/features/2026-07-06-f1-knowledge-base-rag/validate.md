# F-001 — Validation Record

## Automated tests

`uv run pytest tests/ -v` — 12/12 passed, no warnings beyond a pre-existing pydantic
deprecation notice unrelated to this feature. `uv run ruff check app data` — all checks
passed.

| File | Covers |
|---|---|
| `tests/test_rag_chunking.py` | heading-based splitting, oversized-section sub-splitting, content preservation |
| `tests/test_rag_cosine.py` | ranking order, k-limit, score bounds |
| `tests/test_rag_retrieve.py` | top-k ranking, low-confidence flag (positive + negative case), event logging |
| `tests/test_seed.py` | seed populates docs/chunks, idempotent rerun |

All tests use the real `all-MiniLM-L6-v2` model and a real SQLite session — no mocks.

## Acceptance criteria (from spec.md)

**1. "What's your refund window?" retrieves the refund-policy chunk at rank 1.**

PASS. Verified against the fully seeded KB (11 docs, 39 chunks): top result is the
`Refund window` section of `refund-policy.md`, score 0.463.

**2. A question about an unstocked product category ("do you sell refrigerators?") triggers the low-confidence path — no invented answer.**

PASS. Verified against the fully seeded KB: `low_confidence=True`, top score 0.270
(below the 0.35 threshold). No KB doc mentions refrigerators or large appliances, so
this is a genuine confidence signal, not a hardcoded "we don't sell X" answer.

**3. Retrieval latency < 50 ms locally.**

PASS. Measured end-to-end `retrieve()` call (query embedding + cosine rank over all 39
chunks, model pre-warmed): ~31 ms locally.

**4. Re-running `data/seed.py` fully rebuilds embeddings (idempotent).**

PASS. Ran `python -m data.seed` twice against the same database: both runs report
"Seeded 39 KB chunks from 11 docs." — identical counts, no duplication. Also covered by
`test_seed_kb_is_idempotent_on_rerun`.

## Out-of-scope check

No vector DB, reranker, multi-language KB, or KB admin UI was added, per spec.md's
explicit scope cut — confirmed by code review of `app/rag.py` and `data/seed.py`.

## Verdict

4/4 acceptance criteria PASS. Feature complete per spec.
