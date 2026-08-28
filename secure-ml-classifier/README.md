# SecureML Classifier

End-to-end platform for supervised classification on **your own CSV data**: upload a dataset, profile it,
train and tune scikit-learn models with cross-validation, compare them against a majority-class baseline,
inspect metrics visually, and serve predictions — behind an authenticated, audited, rate-limited API.

No dataset ships with the app; every model is trained on files you upload.

```
frontend/  React 19 + TypeScript + Vite + Tailwind + Recharts dashboard
backend/   FastAPI + SQLAlchemy + scikit-learn API
```

## Features

**Machine learning**
- CSV upload with automatic profiling (types, cardinality, missing rates, candidate targets)
- Preprocessing pipeline: median/mode imputation, scaling, one-hot encoding with rare-category folding,
  automatic dropping of high-cardinality identifier columns
- Algorithms: Logistic Regression, Random Forest, Extra Trees, Gradient Boosting, or `auto` to train all
  and keep the best
- Stratified k-fold cross-validation and `RandomizedSearchCV` hyperparameter tuning
- Metrics: accuracy, balanced accuracy, precision, recall, F1, ROC AUC, ROC/PR curves, confusion matrix,
  feature importances, algorithm leaderboard, and a majority-class baseline for honest comparison
- Model registry with versioned joblib artifacts, one deployed model per dataset, and single-record scoring

**Security**
- Argon2id password hashing with a strength policy and automatic rehashing
- Short-lived JWT access tokens + single-use rotating refresh tokens; password change revokes all sessions
- Role-based access control: `admin` (everything, user management, audit log), `analyst` (upload/train/deploy),
  `viewer` (read-only). Non-admins only see their own datasets and runs.
- Account lockout after repeated failed logins; uniform "invalid email or password" responses
- Per-token/IP rate limits on login, refresh, upload, training and prediction
- Upload hardening: extension/content-type allowlist, streaming size cap, row/column caps, UTF-8 validation,
  SHA-256 checksums, filename sanitization, CSV formula-injection neutralization
- Security headers (CSP, HSTS in production, `nosniff`, `DENY` framing, referrer and permissions policy),
  request IDs, generic error responses that never leak stack traces
- Append-only audit log of logins, uploads, training, deployments, predictions and admin changes
- Containers run as a non-root user with `no-new-privileges`

## Quick start (local)

```bash
# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then set APP_SECRET_KEY and the bootstrap admin password
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (separate shell)
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api to port 8000
```

Sign in with the bootstrap admin from `.env` (`admin@example.com` by default) and change the password
immediately from the **Account** page. The bootstrap user is only created when the user table is empty.

## Docker

```bash
export APP_SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
export APP_BOOTSTRAP_ADMIN_PASSWORD='<a strong password>'
docker compose up --build       # UI on http://localhost:8080
```

## Tests and linting

```bash
cd backend  && .venv/bin/ruff check app tests && .venv/bin/pytest -q
cd frontend && npm run lint && npm run build
```

## API

All endpoints are under `/api/v1` and require `Authorization: Bearer <access token>` unless noted.

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| POST | `/auth/login` | public | Issue access + refresh tokens |
| POST | `/auth/refresh` | public | Rotate a refresh token |
| POST | `/auth/logout` | any | Revoke the presented refresh token |
| GET | `/auth/me` | any | Current user |
| POST | `/auth/password` | any | Change password, revoking other sessions |
| POST | `/auth/register` | admin | Create a user |
| GET/PATCH | `/users`, `/users/{id}` | admin | List users, change role or activation |
| GET | `/audit-logs` | admin | Recent audit entries |
| GET | `/stats` | any | Dashboard counters |
| GET/POST/DELETE | `/datasets` | viewer/analyst | List, upload (multipart `file`), delete |
| GET | `/datasets/{id}`, `/datasets/{id}/preview` | any | Profile and sample rows |
| GET | `/runs/algorithms` | any | Available algorithms |
| GET/POST | `/runs` | viewer/analyst | List runs, start a training run |
| GET/DELETE | `/runs/{id}` | viewer/analyst | Run detail with full metrics, delete |
| POST | `/runs/{id}/deploy` | analyst | Mark the run as the active model for its dataset |
| POST | `/runs/{id}/predict` | any | Score up to 500 records |

Interactive docs at `/docs` in non-production environments.

## Configuration

Every setting is an `APP_`-prefixed environment variable — see `backend/.env.example`. In production
(`APP_ENVIRONMENT=production`) the app refuses to start with the development secret key, and `/docs`
and the OpenAPI schema are disabled.

## Operational notes

- Training runs synchronously inside the request; for large datasets put it behind a worker queue.
- SQLite is the default store; point `APP_DATABASE_URL` at PostgreSQL for multi-instance deployments.
- Rate limiting is in-process; use a shared Redis backend for slowapi when running more than one replica.
