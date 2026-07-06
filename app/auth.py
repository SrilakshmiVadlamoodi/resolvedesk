"""Demo identity: a signed, stateless session token — no real auth.

The token is self-describing (customer_id + HMAC signature) rather than a
server-side session_token -> customer_id lookup, so it keeps resolving
correctly across a server restart with zero persisted session state.
"""

import hashlib
import hmac

from app.config import settings


def create_demo_token(customer_id: int) -> str:
    payload = str(customer_id)
    signature = _sign(payload)
    return f"{payload}.{signature}"


def resolve_token(token: str) -> int | None:
    if not token or "." not in token:
        return None

    payload, _, signature = token.partition(".")
    if not hmac.compare_digest(signature, _sign(payload)):
        return None

    try:
        return int(payload)
    except ValueError:
        return None


def _sign(payload: str) -> str:
    return hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
