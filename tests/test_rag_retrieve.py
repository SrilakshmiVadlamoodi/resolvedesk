import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Event, KBChunk, KBDoc
from app.rag import embed_texts, retrieve


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_chunks(session, sections_and_texts):
    doc = KBDoc(slug="test-doc", title="Test Doc")
    session.add(doc)
    session.flush()

    vectors = embed_texts([text for _, text in sections_and_texts])
    for (section, text), vector in zip(sections_and_texts, vectors):
        session.add(
            KBChunk(
                doc_id=doc.id,
                section=section,
                text=text,
                embedding=vector.astype(np.float32).tobytes(),
            )
        )
    session.commit()


KB_FIXTURE = [
    ("Refund window", "Customers may request a refund within 30 days of the delivery date."),
    ("Warranty coverage", "Products are covered by a 12 month warranty against manufacturing defects."),
    ("Shipping timelines", "Standard shipping takes 3 to 5 business days for delivery."),
    ("Cancelling an order", "Orders can be cancelled for free any time before they ship."),
    ("Payment methods", "We accept credit cards, debit cards, UPI, and net banking."),
]


def test_retrieve_returns_top_k_ranked_by_relevance():
    session = make_session()
    seed_chunks(session, KB_FIXTURE)

    result = retrieve(session, "What's your refund window?", top_k=4)

    assert len(result.chunks) == 4
    assert result.chunks[0].section == "Refund window"


def test_retrieve_flags_low_confidence_for_unrelated_query():
    session = make_session()
    seed_chunks(session, KB_FIXTURE)

    result = retrieve(session, "do you sell refrigerators", top_k=4)

    assert result.low_confidence is True


def test_retrieve_does_not_flag_low_confidence_for_clear_match():
    session = make_session()
    seed_chunks(session, KB_FIXTURE)

    result = retrieve(session, "What's your refund window?", top_k=4)

    assert result.low_confidence is False


def test_retrieve_logs_a_retrieval_event_with_query_chunk_ids_and_scores():
    session = make_session()
    seed_chunks(session, KB_FIXTURE)

    retrieve(session, "refund window?", top_k=4)

    events = session.query(Event).filter_by(type="retrieval").all()
    assert len(events) == 1
    assert events[0].payload["query"] == "refund window?"
    assert len(events[0].payload["chunk_ids"]) == 4
    assert len(events[0].payload["scores"]) == 4
