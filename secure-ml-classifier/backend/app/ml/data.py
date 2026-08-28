from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import get_settings

settings = get_settings()

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9 _.\-]")


def sanitize_name(name: str, fallback: str = "dataset") -> str:
    cleaned = SAFE_NAME_RE.sub("_", name).strip().strip(".")
    return (cleaned or fallback)[:120]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_csv_bytes(payload: bytes) -> pd.DataFrame:
    """Parse CSV bytes into a DataFrame with hard limits and no engine surprises."""
    if not payload.strip():
        raise ValueError("Uploaded file is empty.")
    try:
        frame = pd.read_csv(
            io.BytesIO(payload),
            engine="c",
            skipinitialspace=True,
            nrows=settings.max_rows + 1,
            encoding_errors="replace",
        )
    except pd.errors.ParserError as exc:
        raise ValueError(f"Could not parse CSV: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("File is not valid UTF-8 text.") from exc

    if frame.empty:
        raise ValueError("CSV contains no data rows.")
    if len(frame) > settings.max_rows:
        raise ValueError(f"CSV exceeds the {settings.max_rows} row limit.")
    if frame.shape[1] > settings.max_columns:
        raise ValueError(f"CSV exceeds the {settings.max_columns} column limit.")

    frame.columns = [sanitize_name(str(col), "column") for col in frame.columns]
    if len(set(frame.columns)) != len(frame.columns):
        frame.columns = [f"{col}_{idx}" for idx, col in enumerate(frame.columns)]
    return frame


def neutralize_csv_injection(frame: pd.DataFrame) -> pd.DataFrame:
    """Prefix spreadsheet formula triggers so exported cells cannot execute."""
    safe = frame.copy()
    for column in safe.columns:
        if safe[column].dtype == object:
            safe[column] = safe[column].map(
                lambda value: f"'{value}"
                if isinstance(value, str) and value.startswith(FORMULA_PREFIXES)
                else value
            )
    return safe


def store_dataframe(frame: pd.DataFrame, dataset_id: str) -> Path:
    path = settings.storage_dir / "datasets" / f"{dataset_id}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        frame.to_parquet(path, index=False)
    except (ImportError, ValueError):
        path = path.with_suffix(".csv")
        frame.to_csv(path, index=False)
    return path


def load_dataframe(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def profile_dataframe(frame: pd.DataFrame, max_columns: int = 60) -> dict:
    columns = []
    for name in list(frame.columns)[:max_columns]:
        series = frame[name]
        unique = int(series.nunique(dropna=True))
        info = {
            "name": name,
            "dtype": str(series.dtype),
            "missing": int(series.isna().sum()),
            "missing_pct": round(float(series.isna().mean() * 100), 2),
            "unique": unique,
            "kind": "numeric" if pd.api.types.is_numeric_dtype(series) else "categorical",
            "candidate_target": 2 <= unique <= 20,
        }
        if info["kind"] == "numeric" and series.notna().any():
            info["min"] = _finite(series.min())
            info["max"] = _finite(series.max())
            info["mean"] = _finite(series.mean())
        else:
            info["top_values"] = [
                {"value": str(value), "count": int(count)}
                for value, count in series.astype(str).value_counts().head(5).items()
            ]
        columns.append(info)
    return {
        "rows": int(len(frame)),
        "columns": int(frame.shape[1]),
        "truncated_columns": bool(frame.shape[1] > max_columns),
        "column_profiles": columns,
    }


def _finite(value) -> float | None:
    number = float(value)
    return None if not np.isfinite(number) else round(number, 6)
