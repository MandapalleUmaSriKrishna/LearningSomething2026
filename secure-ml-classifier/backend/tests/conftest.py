from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

TMP = Path(tempfile.mkdtemp(prefix="secureml-tests-"))
os.environ.setdefault("APP_DATABASE_URL", f"sqlite:///{TMP / 'test.db'}")
os.environ.setdefault("APP_STORAGE_DIR", str(TMP / "storage"))
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("APP_BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("APP_BOOTSTRAP_ADMIN_PASSWORD", "TestAdminPass!123")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_token(client: TestClient) -> str:
    response = client.post(
        f"{API}/auth/login",
        json={"email": "admin@example.com", "password": "TestAdminPass!123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def auth(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def csv_bytes() -> bytes:
    rng = np.random.default_rng(7)
    size = 400
    income = rng.normal(60_000, 15_000, size)
    tenure = rng.integers(1, 120, size)
    plan = rng.choice(["basic", "pro", "enterprise"], size)
    score = (income / 60_000) + (tenure / 120) + (plan == "enterprise") * 0.6
    churn = np.where(score + rng.normal(0, 0.25, size) > 2.0, "no", "yes")
    frame = pd.DataFrame(
        {
            "income": income.round(2),
            "tenure_months": tenure,
            "plan": plan,
            "churn": churn,
        }
    )
    buffer = io.BytesIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture(scope="session")
def dataset_id(client: TestClient, auth: dict[str, str], csv_bytes: bytes) -> str:
    response = client.post(
        f"{API}/datasets",
        headers=auth,
        files={"file": ("churn.csv", csv_bytes, "text/csv")},
        data={"name": "Churn sample"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]
