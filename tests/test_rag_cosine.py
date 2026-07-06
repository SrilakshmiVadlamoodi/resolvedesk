import numpy as np

from app.rag import cosine_topk


def test_ranks_by_similarity_descending():
    query = np.array([1.0, 0.0])
    matrix = np.array(
        [
            [0.0, 1.0],  # orthogonal, similarity 0
            [1.0, 0.0],  # identical, similarity 1
            [0.7, 0.7],  # similarity ~0.707
        ]
    )

    results = cosine_topk(query, matrix, k=3)

    assert [idx for idx, _ in results] == [1, 2, 0]


def test_respects_k_limit():
    query = np.array([1.0, 0.0])
    matrix = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [-1.0, 0.0]])

    results = cosine_topk(query, matrix, k=2)

    assert len(results) == 2


def test_scores_are_bounded_between_minus_one_and_one():
    query = np.array([1.0, 2.0, 3.0])
    matrix = np.array([[3.0, 2.0, 1.0], [-1.0, -2.0, -3.0]])

    results = cosine_topk(query, matrix, k=2)

    for _, score in results:
        assert -1.0 <= score <= 1.0
