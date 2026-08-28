from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.config import get_settings
from app.database import get_db
from app.models import RefreshToken, Role, User, utcnow
from app.rate_limit import limiter
from app.schemas import (
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.security import (
    create_access_token,
    generate_refresh_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    require_admin,
    validate_password_policy,
    verify_password,
)

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    access_token, expires_in = create_access_token(user)
    raw_refresh, token_hash = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh, expires_in=expires_in)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
def register(
    request: Request,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    """Only admins create accounts — no open self-registration."""
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with that email already exists.")
    validate_password_policy(payload.password)
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    record_audit(
        db,
        action="user.create",
        request=request,
        actor=admin,
        resource=user.email,
        detail={"role": user.role.value},
    )
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.login_rate_limit)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    generic_error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")

    if user is None:
        # Constant-ish work so a missing account is not distinguishable by timing.
        hash_password(payload.password)
        record_audit(db, action="auth.login", request=request, actor_email=email, status="failure")
        raise generic_error

    locked_until = _aware(user.locked_until)
    if locked_until and locked_until > datetime.now(timezone.utc):
        record_audit(
            db,
            action="auth.login",
            request=request,
            actor=user,
            status="locked",
            detail={"locked_until": locked_until.isoformat()},
        )
        raise HTTPException(
            status.HTTP_423_LOCKED, "Account temporarily locked after repeated failed logins."
        )

    if not user.is_active or not verify_password(payload.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_failed_logins:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
        db.commit()
        record_audit(db, action="auth.login", request=request, actor=user, status="failure")
        raise generic_error

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    record_audit(db, action="auth.login", request=request, actor=user)
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("60/hour")
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token_hash = hash_refresh_token(payload.refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(timezone.utc)
    if stored is None or stored.revoked_at is not None or _aware(stored.expires_at) < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token.")
    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token.")
    stored.revoked_at = now  # rotation: a refresh token is single use
    db.commit()
    record_audit(db, action="auth.refresh", request=request, actor=user)
    return _issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def logout(
    request: Request,
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(payload.refresh_token))
    )
    if stored is not None and stored.user_id == user.id:
        stored.revoked_at = datetime.now(timezone.utc)
        db.commit()
    record_audit(db, action="auth.logout", request=request, actor=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
@limiter.limit("10/hour")
def change_password(
    request: Request,
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        record_audit(db, action="auth.password_change", request=request, actor=user, status="failure")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect.")
    validate_password_policy(payload.new_password)
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = utcnow()
    for token in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)):
        token.revoked_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, action="auth.password_change", request=request, actor=user)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


__all__ = ["router", "Role"]
