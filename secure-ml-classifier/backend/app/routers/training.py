from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.config import get_settings
from app.database import get_db
from app.ml.data import load_dataframe
from app.ml.trainer import ALGORITHMS, TrainingConfig, load_pipeline, save_pipeline, train_model
from app.models import Dataset, Role, RunStatus, TrainingRun, User
from app.rate_limit import limiter
from app.schemas import PredictionOut, PredictRequest, PredictResponse, RunOut, RunSummary, TrainRequest
from app.security import get_current_user, require_analyst

settings = get_settings()
router = APIRouter(prefix="/runs", tags=["training"])


def _get_run_or_404(db: Session, run_id: str, user: User) -> TrainingRun:
    run = db.get(TrainingRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Training run not found.")
    if user.role != Role.admin and run.dataset.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Training run not found.")
    return run


@router.get("/algorithms")
def list_algorithms() -> list[dict]:
    return [{"value": "auto", "label": "Auto (compare all)"}] + [
        {"value": key, "label": spec["label"]} for key, spec in ALGORITHMS.items()
    ]


@router.get("", response_model=list[RunSummary])
def list_runs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(TrainingRun).order_by(TrainingRun.created_at.desc())
    if user.role != Role.admin:
        query = query.join(Dataset).where(Dataset.owner_id == user.id)
    return db.scalars(query).all()


@router.post("", response_model=RunOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.train_rate_limit)
def create_run(
    request: Request,
    payload: TrainRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> TrainingRun:
    dataset = db.get(Dataset, payload.dataset_id)
    if dataset is None or (user.role != Role.admin and dataset.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found.")

    run = TrainingRun(
        dataset_id=dataset.id,
        created_by=user.id,
        target_column=payload.target_column,
        algorithm=payload.algorithm,
        status=RunStatus.running,
        config=payload.model_dump(),
    )
    db.add(run)
    db.commit()

    config = TrainingConfig(
        target_column=payload.target_column,
        algorithm=payload.algorithm,
        test_size=payload.test_size,
        cv_folds=payload.cv_folds,
        scoring=payload.scoring,
        tune_hyperparameters=payload.tune_hyperparameters,
        search_iterations=payload.search_iterations,
        feature_columns=payload.feature_columns,
    )
    try:
        result = train_model(load_dataframe(dataset.storage_path), config)
    except ValueError as exc:
        run.status = RunStatus.failed
        run.error_message = str(exc)
        db.commit()
        record_audit(
            db, action="run.train", request=request, actor=user, resource=run.id,
            status="failure", detail={"error": str(exc)},
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected sklearn failure
        run.status = RunStatus.failed
        run.error_message = f"Training failed: {type(exc).__name__}"
        db.commit()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, run.error_message) from exc

    run.algorithm = result.algorithm
    run.metrics = result.metrics
    run.best_params = result.best_params
    run.cv_score = result.cv_score
    run.duration_seconds = result.duration_seconds
    run.artifact_path = str(save_pipeline(result, run.id))
    run.status = RunStatus.succeeded
    db.commit()

    record_audit(
        db, action="run.train", request=request, actor=user, resource=run.id,
        detail={
            "algorithm": run.algorithm,
            "cv_score": run.cv_score,
            "accuracy": result.metrics.get("accuracy"),
        },
    )
    return run


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_run_or_404(db, run_id, user)


@router.post("/{run_id}/deploy", response_model=RunOut)
def deploy_run(
    request: Request,
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> TrainingRun:
    run = _get_run_or_404(db, run_id, user)
    if run.status != RunStatus.succeeded or not run.artifact_path:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only successful runs can be deployed.")
    for other in db.scalars(
        select(TrainingRun).where(TrainingRun.dataset_id == run.dataset_id, TrainingRun.is_deployed.is_(True))
    ):
        other.is_deployed = False
    run.is_deployed = True
    db.commit()
    record_audit(db, action="run.deploy", request=request, actor=user, resource=run.id)
    return run


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_run(
    request: Request,
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> None:
    run = _get_run_or_404(db, run_id, user)
    artifact = Path(run.artifact_path) if run.artifact_path else None
    db.delete(run)
    db.commit()
    if artifact:
        artifact.unlink(missing_ok=True)
    record_audit(db, action="run.delete", request=request, actor=user, resource=run_id)


@router.post("/{run_id}/predict", response_model=PredictResponse)
@limiter.limit("120/minute")
def predict(
    request: Request,
    run_id: str,
    payload: PredictRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PredictResponse:
    run = _get_run_or_404(db, run_id, user)
    if run.status != RunStatus.succeeded or not run.artifact_path:
        raise HTTPException(status.HTTP_409_CONFLICT, "This run has no trained model.")

    bundle = load_pipeline(run.artifact_path)
    pipeline = bundle["pipeline"]
    features: list[str] = bundle["feature_columns"]

    frame = pd.DataFrame(payload.records)
    missing = [column for column in features if column not in frame.columns]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Missing required features: {', '.join(missing[:10])}"
        )
    frame = frame[features]

    labels = [str(label) for label in pipeline.predict(frame)]
    probabilities: list[dict[str, float]] = []
    if hasattr(pipeline, "predict_proba"):
        classes = [str(c) for c in pipeline.classes_]
        for row in pipeline.predict_proba(frame):
            probabilities.append({cls: round(float(p), 4) for cls, p in zip(classes, row, strict=False)})
    else:
        probabilities = [{} for _ in labels]

    record_audit(
        db, action="run.predict", request=request, actor=user, resource=run.id,
        detail={"records": len(payload.records)},
    )
    return PredictResponse(
        run_id=run.id,
        algorithm=run.algorithm,
        predictions=[
            PredictionOut(
                prediction=label,
                confidence=probs.get(label) if probs else None,
                probabilities=probs,
            )
            for label, probs in zip(labels, probabilities, strict=False)
        ],
    )
