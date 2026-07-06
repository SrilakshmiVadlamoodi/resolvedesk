# F-001 — Knowledge Base & Retrieval (RAG)

## Goal
Ground every policy/product answer in VoltKart's knowledge base so the agent never invents policy.

## Behavior
- KB source: `data/kb/*.md` (~10 docs: refund policy, warranty, shipping & delivery, cancellations, payment issues, product FAQs per category, account help).
- At seed time: split docs by heading into chunks of ≤ 300 tokens with section metadata; embed with `all-MiniLM-L6-v2`; store vector as BLOB in `kb_chunks`.
- At query time: embed user message, cosine-rank all chunks (numpy, brute force), return top 4 with scores.
- Chunks are injected into the prompt inside `<kb_context>` delimiters with source labels, plus the instruction: answer only from context; if insufficient, say so and offer escalation.
- Confidence rule: if top score < 0.35, set `low_confidence=True` → agent must not assert policy facts.
- Every retrieval logs an event (query, chunk ids, scores).

## Acceptance criteria
1. "What's your refund window?" retrieves the refund-policy chunk at rank 1.
2. A question about an unstocked product category ("do you sell refrigerators?") triggers the low-confidence path — no invented answer.
3. Retrieval latency < 50 ms locally.
4. Re-running `data/seed.py` fully rebuilds embeddings (idempotent).

## Out of scope
Vector DB, reranking models, multi-language KB, KB admin UI (edit markdown + reseed instead).
