from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Role, RunStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    role: Role = Role.analyst


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a credential
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=512)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class UserOut(ORMModel):
    id: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class DatasetOut(ORMModel):
    id: str
    name: str
    original_filename: str
    size_bytes: int
    row_count: int
    column_count: int
    checksum_sha256: str
    profile: dict[str, Any]
    owner_id: str
    created_at: datetime


class DatasetSummary(ORMModel):
    id: str
    name: str
    row_count: int
    column_count: int
    created_at: datetime


class TrainRequest(BaseModel):
    dataset_id: str
    target_column: str = Field(min_length=1, max_length=255)
    algorithm: Literal[
        "auto", "logistic_regression", "random_forest", "extra_trees", "gradient_boosting"
    ] = "auto"
    test_size: float = Field(default=0.2, ge=0.1, le=0.5)
    cv_folds: int = Field(default=5, ge=2, le=10)
    scoring: Literal["f1_weighted", "accuracy", "balanced_accuracy", "roc_auc"] = "f1_weighted"
    tune_hyperparameters: bool = True
    search_iterations: int = Field(default=12, ge=2, le=40)
    feature_columns: list[str] | None = Field(default=None, max_length=200)


class RunOut(ORMModel):
    id: str
    dataset_id: str
    target_column: str
    algorithm: str
    status: RunStatus
    config: dict[str, Any]
    metrics: dict[str, Any]
    best_params: dict[str, Any]
    cv_score: float | None
    duration_seconds: float | None
    error_message: str | None
    is_deployed: bool
    created_at: datetime


class RunSummary(ORMModel):
    id: str
    dataset_id: str
    algorithm: str
    target_column: str
    status: RunStatus
    cv_score: float | None
    is_deployed: bool
    created_at: datetime


class PredictRequest(BaseModel):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class PredictionOut(BaseModel):
    prediction: str
    confidence: float | None
    probabilities: dict[str, float]


class PredictResponse(BaseModel):
    run_id: str
    algorithm: str
    predictions: list[PredictionOut]


class AuditOut(ORMModel):
    id: str
    actor_email: str | None
    action: str
    resource: str | None
    status: str
    ip_address: str | None
    detail: dict[str, Any]
    created_at: datetime


class StatsOut(BaseModel):
    datasets: int
    runs: int
    deployed_models: int
    users: int
    best_cv_score: float | None
    recent_runs: list[RunSummary]
