from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import KBChunk, KBDoc
from data.seed import seed_kb


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_seed_kb_populates_docs_and_chunks_from_markdown_files():
    session = make_session()

    seed_kb(session)

    assert session.query(KBDoc).count() >= 10
    assert session.query(KBChunk).count() > 0


def test_seed_kb_is_idempotent_on_rerun():
    session = make_session()

    seed_kb(session)
    first_doc_count = session.query(KBDoc).count()
    first_chunk_count = session.query(KBChunk).count()

    seed_kb(session)
    second_doc_count = session.query(KBDoc).count()
    second_chunk_count = session.query(KBChunk).count()

    assert second_doc_count == first_doc_count
    assert second_chunk_count == first_chunk_count
