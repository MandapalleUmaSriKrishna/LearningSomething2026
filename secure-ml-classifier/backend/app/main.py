from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.models import Role, User
from app.rate_limit import limiter
from app.routers import admin, auth, datasets, training
from app.security import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")
settings = get_settings()


def bootstrap_admin() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)) is not None:
            return
        admin_user = User(
            email=settings.bootstrap_admin_email.lower(),
            password_hash=hash_password(settings.bootstrap_admin_password),
            role=Role.admin,
        )
        db.add(admin_user)
        db.commit()
        logger.warning(
            "Created bootstrap admin %s — change this password immediately.", admin_user.email
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    bootstrap_admin()
    if settings.is_production and settings.secret_key.startswith("dev-only"):
        raise RuntimeError("APP_SECRET_KEY must be set to a strong value in production.")
    yield


app = FastAPI(
    title="SecureML Classifier API",
    version="1.0.0",
    description="Secure, auditable AI classification platform for user-supplied CSV data.",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=600,
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Invalid request payload.", "errors": exc.errors()[:10]},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )


api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(datasets.router, prefix=api_prefix)
app.include_router(training.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
