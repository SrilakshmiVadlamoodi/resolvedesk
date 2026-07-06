"""RAG: chunking, embedding, and retrieval over the VoltKart knowledge base."""

import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from app.models import Event, KBChunk

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
LOW_CONFIDENCE_THRESHOLD = 0.35


@dataclass
class Chunk:
    section: str
    text: str


_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def chunk_markdown(text: str, max_tokens: int = 300) -> list[Chunk]:
    """Split markdown into chunks by level-2 heading, sub-splitting oversized
    sections so no chunk exceeds max_tokens words."""
    matches = list(_HEADING_RE.finditer(text))
    chunks: list[Chunk] = []

    for i, match in enumerate(matches):
        section = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        chunks.extend(_split_to_limit(section, body, max_tokens))

    return chunks


def _split_to_limit(section: str, body: str, max_tokens: int) -> list[Chunk]:
    words = body.split()
    if len(words) <= max_tokens:
        return [Chunk(section=section, text=body)]

    result = []
    for i in range(0, len(words), max_tokens):
        result.append(Chunk(section=section, text=" ".join(words[i : i + max_tokens])))
    return result


def cosine_topk(query: np.ndarray, matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Rank rows of `matrix` by cosine similarity to `query`, descending. Returns
    (row_index, score) pairs for the top k."""
    query_norm = query / np.linalg.norm(query)
    matrix_norm = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    scores = np.clip(matrix_norm @ query_norm, -1.0, 1.0)

    ranked_indices = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in ranked_indices]


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_texts(texts: list[str]) -> np.ndarray:
    return get_embedder().encode(texts, convert_to_numpy=True)


@dataclass
class RetrievedChunk:
    id: int
    section: str
    text: str
    score: float


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    low_confidence: bool


def retrieve(
    session: Session,
    query: str,
    top_k: int = 4,
    conversation_id: int | None = None,
) -> RetrievalResult:
    """Embed `query`, cosine-rank all KB chunks, log a retrieval event, and
    return the top_k chunks plus a low-confidence flag (top score < 0.35)."""
    rows = session.query(KBChunk).all()

    query_vector = embed_texts([query])[0]
    matrix = np.stack([np.frombuffer(row.embedding, dtype=np.float32) for row in rows])

    ranked = cosine_topk(query_vector, matrix, k=top_k)
    chunks = [
        RetrievedChunk(id=rows[i].id, section=rows[i].section, text=rows[i].text, score=score)
        for i, score in ranked
    ]
    low_confidence = not chunks or chunks[0].score < LOW_CONFIDENCE_THRESHOLD

    session.add(
        Event(
            conversation_id=conversation_id,
            type="retrieval",
            payload={
                "query": query,
                "chunk_ids": [c.id for c in chunks],
                "scores": [c.score for c in chunks],
            },
        )
    )
    session.commit()

    return RetrievalResult(chunks=chunks, low_confidence=low_confidence)
