from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.config import get_settings
from app.database import get_db
from app.ml.data import (
    load_dataframe,
    neutralize_csv_injection,
    profile_dataframe,
    read_csv_bytes,
    sanitize_name,
    sha256_bytes,
    store_dataframe,
)
from app.models import Dataset, Role, User
from app.rate_limit import limiter
from app.schemas import DatasetOut, DatasetSummary
from app.security import get_current_user, require_analyst

settings = get_settings()
router = APIRouter(prefix="/datasets", tags=["datasets"])

ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel"}


def _visible_datasets(db: Session, user: User):
    query = select(Dataset).order_by(Dataset.created_at.desc())
    if user.role != Role.admin:
        query = query.where(Dataset.owner_id == user.id)
    return db.scalars(query).all()


def _get_dataset_or_404(db: Session, dataset_id: str, user: User) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or (user.role != Role.admin and dataset.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found.")
    return dataset


@router.get("", response_model=list[DatasetSummary])
def list_datasets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _visible_datasets(db, user)


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> Dataset:
    filename = Path(file.filename or "upload.csv").name
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only .csv files are accepted.")
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported content type '{file.content_type}'."
        )

    payload = bytearray()
    while chunk := await file.read(1024 * 1024):
        payload.extend(chunk)
        if len(payload) > settings.max_upload_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit.",
            )
    raw = bytes(payload)

    try:
        frame = neutralize_csv_injection(read_csv_bytes(raw))
    except ValueError as exc:
        record_audit(
            db, action="dataset.upload", request=request, actor=user, status="rejected",
            resource=filename, detail={"reason": str(exc)},
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    checksum = sha256_bytes(raw)
    duplicate = db.scalar(
        select(Dataset).where(Dataset.checksum_sha256 == checksum, Dataset.owner_id == user.id)
    )
    if duplicate is not None:
        return duplicate

    dataset = Dataset(
        name=sanitize_name(name or Path(filename).stem),
        original_filename=sanitize_name(filename, "upload.csv"),
        storage_path="",
        checksum_sha256=checksum,
        size_bytes=len(raw),
        row_count=int(len(frame)),
        column_count=int(frame.shape[1]),
        profile=profile_dataframe(frame),
        owner_id=user.id,
    )
    db.add(dataset)
    db.flush()
    dataset.storage_path = str(store_dataframe(frame, dataset.id))
    db.commit()
    record_audit(
        db,
        action="dataset.upload",
        request=request,
        actor=user,
        resource=dataset.id,
        detail={"rows": dataset.row_count, "columns": dataset.column_count, "sha256": checksum},
    )
    return dataset


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_dataset_or_404(db, dataset_id, user)


@router.get("/{dataset_id}/preview")
def preview_dataset(
    dataset_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    dataset = _get_dataset_or_404(db, dataset_id, user)
    frame = load_dataframe(dataset.storage_path).head(max(1, min(limit, 100)))
    return {
        "columns": list(frame.columns),
        "rows": frame.astype(object).where(frame.notna(), None).to_dict(orient="records"),
    }


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_dataset(
    request: Request,
    dataset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> None:
    dataset = _get_dataset_or_404(db, dataset_id, user)
    path = Path(dataset.storage_path)
    db.delete(dataset)
    db.commit()
    path.unlink(missing_ok=True)
    record_audit(db, action="dataset.delete", request=request, actor=user, resource=dataset_id)
