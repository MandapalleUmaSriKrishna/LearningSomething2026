from fastapi.testclient import TestClient

API = "/api/v1"


def test_health_and_security_headers(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in response.headers
    assert "x-request-id" in response.headers


def test_protected_route_requires_token(client: TestClient) -> None:
    assert client.get(f"{API}/datasets").status_code == 401
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_login_rejects_bad_password_generically(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/login", json={"email": "admin@example.com", "password": "WrongPassword!1"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_me_returns_admin(client: TestClient, auth: dict) -> None:
    body = client.get(f"{API}/auth/me", headers=auth).json()
    assert body["email"] == "admin@example.com"
    assert body["role"] == "admin"


def test_refresh_token_rotates_and_is_single_use(client: TestClient) -> None:
    tokens = client.post(
        f"{API}/auth/login", json={"email": "admin@example.com", "password": "TestAdminPass!123"}
    ).json()
    first = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    replay = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401


def test_weak_password_rejected_on_register(client: TestClient, auth: dict) -> None:
    response = client.post(
        f"{API}/auth/register",
        headers=auth,
        json={"email": "weak@example.com", "password": "alllowercaseletters"},
    )
    assert response.status_code == 422


def test_rbac_viewer_cannot_upload(client: TestClient, auth: dict, csv_bytes: bytes) -> None:
    created = client.post(
        f"{API}/auth/register",
        headers=auth,
        json={"email": "viewer@example.com", "password": "ViewerPass!12345", "role": "viewer"},
    )
    assert created.status_code == 201
    token = client.post(
        f"{API}/auth/login", json={"email": "viewer@example.com", "password": "ViewerPass!12345"}
    ).json()["access_token"]
    viewer_auth = {"Authorization": f"Bearer {token}"}

    upload = client.post(
        f"{API}/datasets", headers=viewer_auth, files={"file": ("x.csv", csv_bytes, "text/csv")}
    )
    assert upload.status_code == 403
    assert client.get(f"{API}/audit-logs", headers=viewer_auth).status_code == 403
    assert client.get(f"{API}/datasets", headers=viewer_auth).status_code == 200
