from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()


def rate_limit_key(request: Request) -> str:
    """Prefer the authenticated subject so one noisy IP cannot exhaust everyone's quota."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return f"token:{auth[7:][:32]}"
    return get_remote_address(request) or "anonymous"


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=[settings.default_rate_limit],
    headers_enabled=False,
)
