from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.database import get_db
from app.models import AuditLog, Dataset, Role, RunStatus, TrainingRun, User
from app.schemas import AuditOut, StatsOut, UserOut, UserUpdate
from app.security import get_current_user, require_admin

router = APIRouter(tags=["admin"])


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StatsOut:
    dataset_query = select(Dataset)
    run_query = select(TrainingRun)
    if user.role != Role.admin:
        dataset_query = dataset_query.where(Dataset.owner_id == user.id)
        run_query = run_query.join(Dataset).where(Dataset.owner_id == user.id)

    datasets = db.scalars(dataset_query).all()
    runs = db.scalars(run_query.order_by(TrainingRun.created_at.desc())).all()
    successful = [run.cv_score for run in runs if run.cv_score is not None]
    return StatsOut(
        datasets=len(datasets),
        runs=len(runs),
        deployed_models=sum(1 for run in runs if run.is_deployed),
        users=db.scalar(select(func.count(User.id))) or 0,
        best_cv_score=round(max(successful), 4) if successful else None,
        recent_runs=runs[:5],
    )


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(User).order_by(User.created_at.desc())).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    request: Request,
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if target.id == admin.id and (payload.role not in (None, Role.admin) or payload.is_active is False):
        raise HTTPException(status.HTTP_409_CONFLICT, "Admins cannot demote or disable themselves.")
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
    db.commit()
    record_audit(
        db, action="user.update", request=request, actor=admin, resource=target.email,
        detail=payload.model_dump(exclude_none=True, mode="json"),
    )
    return target


@router.get("/audit-logs", response_model=list[AuditOut])
def audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 500)))
    ).all()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.scalar(select(func.count(User.id)))
    return {"status": "ok", "runs_pending": db.scalar(
        select(func.count(TrainingRun.id)).where(TrainingRun.status == RunStatus.running)
    ) or 0}
