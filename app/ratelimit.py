"""In-memory sliding-window rate limiter, per session token.

Resetting on server restart is acceptable for a rate limiter (unlike
conversation state) — it's a soft protection on API spend, not correctness.
"""

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, limit: int = 20, window_seconds: float = 60.0, now=time.monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self._now = now
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, token: str) -> bool:
        now = self._now()
        cutoff = now - self.window_seconds
        hits = [t for t in self._hits[token] if t > cutoff]

        if len(hits) >= self.limit:
            self._hits[token] = hits
            return False

        hits.append(now)
        self._hits[token] = hits
        return True


chat_rate_limiter = RateLimiter(limit=20, window_seconds=60.0)
