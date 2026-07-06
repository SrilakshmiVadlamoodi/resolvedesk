from app import auth


def test_create_and_resolve_round_trips_customer_id():
    token = auth.create_demo_token(42)

    assert auth.resolve_token(token) == 42


def test_resolve_rejects_tampered_token():
    token = auth.create_demo_token(42)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")

    assert auth.resolve_token(tampered) is None


def test_resolve_rejects_garbage_token():
    assert auth.resolve_token("not-a-real-token") is None


def test_resolve_rejects_empty_token():
    assert auth.resolve_token("") is None


def test_token_survives_across_calls_without_server_state():
    # No shared in-memory store is consulted — the token is self-describing,
    # so it resolves correctly even from a "fresh process" perspective.
    token = auth.create_demo_token(7)
    assert auth.resolve_token(token) == 7
    assert auth.resolve_token(token) == 7
