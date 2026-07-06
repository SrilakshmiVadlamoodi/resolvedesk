# F-001 — Implementation Notes

## What was built

- `data/kb/*.md` — 11 VoltKart knowledge base docs: refund policy, warranty policy,
  shipping & delivery, cancellations, payment issues, three product-FAQ docs (audio,
  smart home, wearables), account help, returns process, discounts & promotions. Each
  doc is a `#` title followed by `##` sections — the section boundary is the chunk
  boundary.
- `app/models.py` — `KBDoc` (slug, title), `KBChunk` (doc_id, section, text, embedding
  BLOB), `Event` (conversation_id, type, payload JSON, created_at). `app/db.py` holds
  the SQLAlchemy engine/session factory.
- `app/rag.py`:
  - `chunk_markdown(text, max_tokens=300)` — splits on `##` headings; sections longer
    than `max_tokens` words are sub-split (word count is used as the token proxy) so no
    chunk exceeds the limit while section metadata is preserved across sub-chunks.
  - `cosine_topk(query, matrix, k)` — brute-force cosine similarity via numpy,
    normalizes both sides, clips to [-1, 1] to guard against float overshoot, returns
    the top-k `(index, score)` pairs.
  - `embed_texts(texts)` — wraps a module-cached `SentenceTransformer("all-MiniLM-L6-v2")`.
  - `retrieve(session, query, top_k=4, conversation_id=None)` — embeds the query, ranks
    all `kb_chunks` rows, flags `low_confidence` when the top score is below 0.35, and
    always logs a `retrieval` event (query, chunk_ids, scores) before returning.
- `data/seed.py` — `seed_kb(session)` deletes existing `kb_docs`/`kb_chunks` rows, then
  re-reads every `data/kb/*.md`, chunks it, embeds all chunks in one batch call, and
  inserts fresh rows. `main()` creates tables and runs it end-to-end via
  `python -m data.seed`.
- `pyproject.toml` — added `[tool.setuptools.packages.find]` (the flat layout has four
  top-level dirs — `app`, `data`, `web`, `evals` — which setuptools can't
  auto-discover without an explicit include list).

## Key decisions

- **Word count as token proxy**, not a real tokenizer. Fast, dependency-free, and close
  enough at this KB size (~40 chunks) that the 300-token ceiling is never a binding
  constraint in practice — sections are naturally short.
- **Idempotent seed via delete-then-insert**, not upsert-by-slug. Simpler, and correct
  for this KB size; matches the "reproducible demo database" requirement in
  tech-stack.md.
- **Confidence threshold left at the spec's 0.35** rather than tuned — validated
  empirically against the real KB (see validate.md) rather than assumed.
- **No vector DB / reranker**, per the spec's explicit out-of-scope list — numpy brute
  force over ~40 chunks is sub-50ms, so there's no scale pressure to justify one.

## Deviations from spec

None. All behavior described in spec.md is implemented as specified.

## Follow-ups (not blocking F-001)

- `events.conversation_id` has no FK constraint yet — the `conversations` table doesn't
  exist until a later feature. Will add the FK when that table lands.
- KB doc count is 11, not the spec's approximate "~10" — one extra doc
  (`discounts-promotions.md`) was added for FAQ coverage breadth; still well within the
  KB-admin-UI-not-needed scale assumption.
