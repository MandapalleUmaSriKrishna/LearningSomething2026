from fastapi.testclient import TestClient

API = "/api/v1"


def test_upload_profiles_dataset(client: TestClient, auth: dict, dataset_id: str) -> None:
    body = client.get(f"{API}/datasets/{dataset_id}", headers=auth).json()
    assert body["row_count"] == 400
    assert body["column_count"] == 4
    names = {column["name"] for column in body["profile"]["column_profiles"]}
    assert {"income", "tenure_months", "plan", "churn"} <= names


def test_upload_rejects_non_csv(client: TestClient, auth: dict) -> None:
    response = client.post(
        f"{API}/datasets", headers=auth, files={"file": ("evil.exe", b"MZ\x00", "application/octet-stream")}
    )
    assert response.status_code == 415


def test_csv_formula_injection_is_neutralized(client: TestClient, auth: dict) -> None:
    payload = b"label,note\nyes,=cmd|'/c calc'!A1\nno,safe\n"
    response = client.post(
        f"{API}/datasets", headers=auth, files={"file": ("inject.csv", payload, "text/csv")}
    )
    assert response.status_code == 201
    preview = client.get(f"{API}/datasets/{response.json()['id']}/preview", headers=auth).json()
    assert preview["rows"][0]["note"].startswith("'=")


def test_train_predict_and_deploy(client: TestClient, auth: dict, dataset_id: str) -> None:
    run = client.post(
        f"{API}/runs",
        headers=auth,
        json={
            "dataset_id": dataset_id,
            "target_column": "churn",
            "algorithm": "random_forest",
            "tune_hyperparameters": False,
            "cv_folds": 3,
        },
    )
    assert run.status_code == 201, run.text
    body = run.json()
    assert body["status"] == "succeeded"
    metrics = body["metrics"]
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert metrics["accuracy"] >= metrics["baseline"]["accuracy"]
    assert metrics["confusion_matrix"]
    assert metrics["feature_importances"]
    assert metrics["cv"]["folds"] == 3

    run_id = body["id"]
    deployed = client.post(f"{API}/runs/{run_id}/deploy", headers=auth)
    assert deployed.status_code == 200 and deployed.json()["is_deployed"] is True

    prediction = client.post(
        f"{API}/runs/{run_id}/predict",
        headers=auth,
        json={"records": [{"income": 82000, "tenure_months": 90, "plan": "enterprise"}]},
    )
    assert prediction.status_code == 200
    first = prediction.json()["predictions"][0]
    assert first["prediction"] in {"yes", "no"}
    assert 0.0 <= first["confidence"] <= 1.0


def test_train_rejects_unknown_target(client: TestClient, auth: dict, dataset_id: str) -> None:
    response = client.post(
        f"{API}/runs",
        headers=auth,
        json={"dataset_id": dataset_id, "target_column": "missing_column", "tune_hyperparameters": False},
    )
    assert response.status_code == 422


def test_predict_requires_all_features(client: TestClient, auth: dict, dataset_id: str) -> None:
    run_id = client.post(
        f"{API}/runs",
        headers=auth,
        json={
            "dataset_id": dataset_id,
            "target_column": "churn",
            "algorithm": "logistic_regression",
            "tune_hyperparameters": False,
            "cv_folds": 3,
        },
    ).json()["id"]
    response = client.post(
        f"{API}/runs/{run_id}/predict", headers=auth, json={"records": [{"income": 1000}]}
    )
    assert response.status_code == 422


def test_audit_log_records_actions(client: TestClient, auth: dict) -> None:
    logs = client.get(f"{API}/audit-logs", headers=auth).json()
    actions = {entry["action"] for entry in logs}
    assert {"auth.login", "dataset.upload", "run.train"} <= actions


def test_stats_endpoint(client: TestClient, auth: dict) -> None:
    body = client.get(f"{API}/stats", headers=auth).json()
    assert body["datasets"] >= 1 and body["runs"] >= 1
    assert body["deployed_models"] >= 1
