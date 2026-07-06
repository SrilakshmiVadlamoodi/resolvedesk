from app import ratelimit


def test_allows_requests_under_the_limit():
    limiter = ratelimit.RateLimiter(limit=3, window_seconds=60)

    assert limiter.allow("token-a") is True
    assert limiter.allow("token-a") is True
    assert limiter.allow("token-a") is True


def test_blocks_requests_over_the_limit():
    limiter = ratelimit.RateLimiter(limit=3, window_seconds=60)
    for _ in range(3):
        limiter.allow("token-a")

    assert limiter.allow("token-a") is False


def test_limits_are_independent_per_token():
    limiter = ratelimit.RateLimiter(limit=1, window_seconds=60)

    assert limiter.allow("token-a") is True
    assert limiter.allow("token-b") is True


def test_old_requests_fall_out_of_the_window():
    clock = {"t": 0.0}
    limiter = ratelimit.RateLimiter(limit=1, window_seconds=60, now=lambda: clock["t"])

    assert limiter.allow("token-a") is True
    assert limiter.allow("token-a") is False

    clock["t"] = 61.0
    assert limiter.allow("token-a") is True
