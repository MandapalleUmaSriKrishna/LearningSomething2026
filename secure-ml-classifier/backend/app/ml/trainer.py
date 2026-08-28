from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.config import get_settings

settings = get_settings()

ALGORITHMS: dict[str, dict[str, Any]] = {
    "logistic_regression": {
        "label": "Logistic Regression",
        "factory": lambda: LogisticRegression(max_iter=2000, class_weight="balanced"),
        "search_space": {
            "model__C": [0.01, 0.1, 0.5, 1.0, 3.0, 10.0],
            "model__penalty": ["l2"],
            "model__solver": ["lbfgs", "liblinear"],
        },
    },
    "random_forest": {
        "label": "Random Forest",
        "factory": lambda: RandomForestClassifier(random_state=42, class_weight="balanced_subsample"),
        "search_space": {
            "model__n_estimators": [200, 300, 500],
            "model__max_depth": [None, 6, 12, 20],
            "model__min_samples_leaf": [1, 2, 4],
            "model__max_features": ["sqrt", "log2"],
        },
    },
    "extra_trees": {
        "label": "Extra Trees",
        "factory": lambda: ExtraTreesClassifier(random_state=42, class_weight="balanced"),
        "search_space": {
            "model__n_estimators": [200, 400],
            "model__max_depth": [None, 8, 16],
            "model__min_samples_leaf": [1, 2, 4],
        },
    },
    "gradient_boosting": {
        "label": "Gradient Boosting",
        "factory": lambda: GradientBoostingClassifier(random_state=42),
        "search_space": {
            "model__n_estimators": [100, 200, 300],
            "model__learning_rate": [0.03, 0.05, 0.1, 0.2],
            "model__max_depth": [2, 3, 4],
        },
    },
}


@dataclass
class TrainingConfig:
    target_column: str
    algorithm: str = "auto"
    test_size: float = 0.2
    cv_folds: int = 5
    scoring: str = "f1_weighted"
    tune_hyperparameters: bool = True
    search_iterations: int = 12
    feature_columns: list[str] | None = None
    random_state: int = 42


@dataclass
class TrainingResult:
    algorithm: str
    metrics: dict[str, Any]
    best_params: dict[str, Any]
    cv_score: float
    duration_seconds: float
    pipeline: Pipeline = field(repr=False)
    label_classes: list[str] = field(default_factory=list)
    feature_columns: list[str] = field(default_factory=list)


def build_preprocessor(frame: pd.DataFrame) -> ColumnTransformer:
    numeric = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
    categorical = [c for c in frame.columns if c not in numeric]
    numeric_pipe = Pipeline(
        [("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
    )
    categorical_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            (
                "encode",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist", min_frequency=0.01, max_categories=40
                ),
            ),
        ]
    )
    return ColumnTransformer(
        [("numeric", numeric_pipe, numeric), ("categorical", categorical_pipe, categorical)],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def prepare_xy(frame: pd.DataFrame, config: TrainingConfig) -> tuple[pd.DataFrame, pd.Series]:
    if config.target_column not in frame.columns:
        raise ValueError(f"Target column '{config.target_column}' is not in the dataset.")

    features = config.feature_columns or [c for c in frame.columns if c != config.target_column]
    features = [c for c in features if c != config.target_column and c in frame.columns]
    if not features:
        raise ValueError("No feature columns available for training.")

    data = frame[features + [config.target_column]].dropna(subset=[config.target_column])
    y = data[config.target_column]
    if y.nunique() < 2:
        raise ValueError("Target column must contain at least two classes.")
    if y.nunique() > 50:
        raise ValueError("Target column has too many distinct values for classification.")
    counts = y.value_counts()
    if counts.min() < 2:
        raise ValueError("Every target class needs at least 2 samples.")
    if len(data) < 20:
        raise ValueError("At least 20 usable rows are required to train.")

    # High-cardinality free-text identifiers add noise; drop them.
    x = data[features]
    droppable = [
        column
        for column in x.columns
        if not pd.api.types.is_numeric_dtype(x[column]) and x[column].nunique() > max(50, 0.5 * len(x))
    ]
    x = x.drop(columns=droppable)
    if x.empty or x.shape[1] == 0:
        raise ValueError("No usable feature columns remain after cleaning.")
    return x, y.astype(str)


def train_model(frame: pd.DataFrame, config: TrainingConfig) -> TrainingResult:
    started = time.perf_counter()
    x, y = prepare_xy(frame, config)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=config.test_size, random_state=config.random_state, stratify=y
    )
    folds = max(2, min(config.cv_folds, int(y_train.value_counts().min())))
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=config.random_state)

    candidates = list(ALGORITHMS) if config.algorithm == "auto" else [config.algorithm]
    if any(name not in ALGORITHMS for name in candidates):
        raise ValueError(f"Unknown algorithm '{config.algorithm}'.")

    leaderboard: list[dict[str, Any]] = []
    best: tuple[float, str, Pipeline, dict[str, Any]] | None = None

    for name in candidates:
        spec = ALGORITHMS[name]
        pipeline = Pipeline(
            [("preprocess", build_preprocessor(x_train)), ("model", spec["factory"]())]
        )
        if config.tune_hyperparameters:
            search = RandomizedSearchCV(
                pipeline,
                spec["search_space"],
                n_iter=config.search_iterations,
                scoring=config.scoring,
                cv=cv,
                random_state=config.random_state,
                n_jobs=-1,
                error_score=0.0,
                refit=True,
            )
            search.fit(x_train, y_train)
            fitted, score, params = search.best_estimator_, float(search.best_score_), search.best_params_
        else:
            from sklearn.model_selection import cross_val_score

            scores = cross_val_score(pipeline, x_train, y_train, cv=cv, scoring=config.scoring, n_jobs=-1)
            pipeline.fit(x_train, y_train)
            fitted, score, params = pipeline, float(np.mean(scores)), {}

        leaderboard.append({"algorithm": name, "label": spec["label"], "cv_score": round(score, 4)})
        if best is None or score > best[0]:
            best = (score, name, fitted, params)

    assert best is not None
    cv_score, algorithm, pipeline, best_params = best
    metrics = evaluate(pipeline, x_train, y_train, x_test, y_test, config)
    metrics["leaderboard"] = sorted(leaderboard, key=lambda item: item["cv_score"], reverse=True)
    metrics["cv"] = {"folds": folds, "scoring": config.scoring, "mean_score": round(cv_score, 4)}
    metrics["baseline"] = baseline_metrics(y_train, y_test)

    return TrainingResult(
        algorithm=algorithm,
        metrics=metrics,
        best_params={k: _jsonable(v) for k, v in best_params.items()},
        cv_score=cv_score,
        duration_seconds=round(time.perf_counter() - started, 3),
        pipeline=pipeline,
        label_classes=sorted(y.unique().tolist()),
        feature_columns=list(x.columns),
    )


def baseline_metrics(y_train: pd.Series, y_test: pd.Series) -> dict[str, Any]:
    majority = y_train.value_counts().idxmax()
    predictions = pd.Series([majority] * len(y_test), index=y_test.index)
    return {
        "strategy": "majority_class",
        "class": str(majority),
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "f1_weighted": round(float(f1_score(y_test, predictions, average="weighted", zero_division=0)), 4),
    }


def evaluate(
    pipeline: Pipeline,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    config: TrainingConfig,
) -> dict[str, Any]:
    predictions = pipeline.predict(x_test)
    classes = list(pipeline.classes_)
    average = "binary" if len(classes) == 2 else "weighted"
    positive = classes[1] if len(classes) == 2 else None

    metrics: dict[str, Any] = {
        "accuracy": _round(accuracy_score(y_test, predictions)),
        "balanced_accuracy": _round(balanced_accuracy_score(y_test, predictions)),
        "precision": _round(
            precision_score(y_test, predictions, average=average, pos_label=positive, zero_division=0)
            if positive is not None
            else precision_score(y_test, predictions, average=average, zero_division=0)
        ),
        "recall": _round(
            recall_score(y_test, predictions, average=average, pos_label=positive, zero_division=0)
            if positive is not None
            else recall_score(y_test, predictions, average=average, zero_division=0)
        ),
        "f1": _round(
            f1_score(y_test, predictions, average=average, pos_label=positive, zero_division=0)
            if positive is not None
            else f1_score(y_test, predictions, average=average, zero_division=0)
        ),
        "classes": [str(c) for c in classes],
        "test_samples": int(len(y_test)),
        "train_samples": int(len(y_train)),
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=classes).tolist(),
        "class_distribution": {str(k): int(v) for k, v in y_train.value_counts().items()},
    }

    if hasattr(pipeline, "predict_proba"):
        proba = pipeline.predict_proba(x_test)
        if len(classes) == 2:
            scores = proba[:, 1]
            binary_truth = (y_test.to_numpy() == classes[1]).astype(int)
            metrics["roc_auc"] = _round(roc_auc_score(binary_truth, scores))
            fpr, tpr, _ = roc_curve(binary_truth, scores)
            metrics["roc_curve"] = _downsample(
                [{"fpr": _round(f), "tpr": _round(t)} for f, t in zip(fpr, tpr, strict=False)]
            )
            precisions, recalls, _ = precision_recall_curve(binary_truth, scores)
            metrics["pr_curve"] = _downsample(
                [
                    {"recall": _round(r), "precision": _round(p)}
                    for p, r in zip(precisions, recalls, strict=False)
                ]
            )
        else:
            try:
                metrics["roc_auc"] = _round(
                    roc_auc_score(y_test, proba, multi_class="ovr", average="weighted", labels=classes)
                )
            except ValueError:
                metrics["roc_auc"] = None

    metrics["feature_importances"] = feature_importances(pipeline)
    metrics["config"] = {
        "target_column": config.target_column,
        "test_size": config.test_size,
        "scoring": config.scoring,
        "tuned": config.tune_hyperparameters,
    }
    return metrics


def feature_importances(pipeline: Pipeline, top_n: int = 15) -> list[dict[str, Any]]:
    model = pipeline.named_steps["model"]
    try:
        names = list(pipeline.named_steps["preprocess"].get_feature_names_out())
    except Exception:  # pragma: no cover - defensive
        return []

    if hasattr(model, "feature_importances_"):
        values = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, "coef_"):
        coef = np.asarray(model.coef_, dtype=float)
        values = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef)
    else:
        return []

    if len(values) != len(names):
        return []
    ranked = sorted(zip(names, values, strict=False), key=lambda item: item[1], reverse=True)[:top_n]
    return [{"feature": name, "importance": _round(value)} for name, value in ranked]


def save_pipeline(result: TrainingResult, run_id: str) -> Path:
    path = settings.storage_dir / "models" / f"{run_id}.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": result.pipeline,
            "feature_columns": result.feature_columns,
            "classes": result.label_classes,
            "algorithm": result.algorithm,
        },
        path,
        compress=3,
    )
    return path


def load_pipeline(path: str | Path) -> dict[str, Any]:
    return joblib.load(Path(path))


def _round(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(number) else round(number, 4)


def _downsample(points: list[dict[str, Any]], limit: int = 120) -> list[dict[str, Any]]:
    if len(points) <= limit:
        return points
    step = len(points) / limit
    sampled = [points[int(index * step)] for index in range(limit)]
    sampled.append(points[-1])
    return sampled


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.integer | np.floating):
        return value.item()
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value
