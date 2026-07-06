from app.rag import chunk_markdown


def test_splits_by_heading_into_one_chunk_per_section():
    text = (
        "# Refund Policy\n\n"
        "## Refund window\n"
        "Customers may request a refund within 30 days.\n\n"
        "## Refund amount\n"
        "Approved refunds are issued within 5-7 business days.\n"
    )

    chunks = chunk_markdown(text, max_tokens=300)

    assert len(chunks) == 2
    assert chunks[0].section == "Refund window"
    assert "30 days" in chunks[0].text
    assert chunks[1].section == "Refund amount"
    assert "5-7 business days" in chunks[1].text


def test_splits_oversized_section_into_multiple_chunks_under_limit():
    body = " ".join(f"word{i}" for i in range(700))
    text = f"# Doc\n\n## Big section\n{body}\n"

    chunks = chunk_markdown(text, max_tokens=300)

    assert len(chunks) > 1
    assert all(c.section == "Big section" for c in chunks)
    for c in chunks:
        assert len(c.text.split()) <= 300


def test_reassembles_to_original_word_content_across_split_chunks():
    body = " ".join(f"word{i}" for i in range(700))
    text = f"# Doc\n\n## Big section\n{body}\n"

    chunks = chunk_markdown(text, max_tokens=300)

    reassembled = " ".join(c.text for c in chunks)
    assert reassembled.split() == body.split()
