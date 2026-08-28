from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit(
    db: Session,
    *,
    action: str,
    request: Request | None = None,
    actor: User | None = None,
    actor_email: str | None = None,
    resource: str | None = None,
    status: str = "success",
    detail: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else actor_email,
        action=action,
        resource=resource,
        status=status,
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("user-agent", "")[:255] if request else None),
        detail=detail or {},
    )
    db.add(entry)
    db.commit()
    return entry


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None
