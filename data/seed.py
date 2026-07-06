"""Reproducible demo database. Run: python -m data.seed"""

from pathlib import Path

from app.db import Base, engine, get_session
from app.models import KBChunk, KBDoc
from app.rag import chunk_markdown, embed_texts

KB_DIR = Path(__file__).parent / "kb"


def _title_from_markdown(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


def seed_kb(session) -> None:
    """Rebuild kb_docs/kb_chunks from data/kb/*.md. Safe to rerun — clears
    existing rows first so re-seeding never duplicates or drifts."""
    session.query(KBChunk).delete()
    session.query(KBDoc).delete()
    session.commit()

    for path in sorted(KB_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        doc = KBDoc(slug=path.stem, title=_title_from_markdown(text))
        session.add(doc)
        session.flush()

        chunks = chunk_markdown(text)
        if not chunks:
            continue
        vectors = embed_texts([c.text for c in chunks])
        for chunk, vector in zip(chunks, vectors):
            session.add(
                KBChunk(
                    doc_id=doc.id,
                    section=chunk.section,
                    text=chunk.text,
                    embedding=vector.astype("float32").tobytes(),
                )
            )
    session.commit()


def main() -> None:
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        seed_kb(session)
        doc_count = session.query(KBDoc).count()
        chunk_count = session.query(KBChunk).count()
        print(f"Seeded {chunk_count} KB chunks from {doc_count} docs.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
