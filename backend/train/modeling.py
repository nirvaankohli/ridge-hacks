from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


LATITUDE_BANDS = [35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0]
DEBUG = True


def print_if_debug(message: str) -> None:
    if DEBUG:
        print(message)


@dataclass(slots=True)
class TrainingResult:
    artifact_path: Path
    metrics_path: Path
    row_count: int
    class_labels: list[str]


def get_viewline_latitude(kp: float) -> float:
    return max(40.0, 67.0 - kp * 2.5)


def derive_local_risk_label(kp: float, latitude: float) -> str:
    abs_lat = abs(latitude)
    viewline = get_viewline_latitude(kp)

    if kp < 5:
        return "quiet"
    if kp >= 8 and abs_lat >= max(45.0, viewline - 2):
        return "severe"
    if kp >= 6 and abs_lat >= max(50.0, viewline):
        return "high"
    if abs_lat >= max(55.0, viewline + 3):
        return "moderate"
    return "watch"


def expand_rows_by_latitude(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        kp = float(record["target_kp"])
        for latitude in LATITUDE_BANDS:
            row = dict(record)
            row["latitude"] = latitude
            row["latitude_abs"] = abs(latitude)
            row["viewline_latitude"] = get_viewline_latitude(kp)
            row["risk_label"] = derive_local_risk_label(kp, latitude)
            rows.append(row)
    return pd.DataFrame(rows)


def train_risk_model(dataset: pd.DataFrame, artifact_dir: Path) -> TrainingResult:
    print_if_debug(f"training model on dataset with {len(dataset)} rows")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    expanded = expand_rows_by_latitude(dataset).dropna()

    print_if_debug(f"expanded dataset to {len(expanded)} rows after latitude expansion")

    feature_columns = [
        "latitude",
        "latitude_abs",
        "cme_count_24h",
        "earth_directed_cme_count_72h",
        "max_cme_speed_72h",
        "mean_cme_speed_72h",
        "mean_cme_half_angle_72h",
        "impact_count_24h",
        "flare_count_24h",
        "m_flare_count_72h",
        "x_flare_count_72h",
        "prior_day_max_kp",
        "prior_3day_mean_kp",
    ]

    X = expanded[feature_columns]
    y = expanded["risk_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    label_encoder = LabelEncoder()
    y_train_encoded = label_encoder.fit_transform(y_train)

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="multi:softprob",
        eval_metric="mlogloss",
        random_state=42,
    )
    model.fit(X_train, y_train_encoded)

    prediction_encoded = model.predict(X_test)
    predictions = label_encoder.inverse_transform(prediction_encoded)
    report = classification_report(y_test, predictions, output_dict=False)

    artifact_path = artifact_dir / "solar_storm_risk_model.joblib"
    metrics_path = artifact_dir / "solar_storm_risk_metrics.txt"

    joblib.dump(
        {
            "model": model,
            "feature_columns": feature_columns,
            "labels": sorted(y.unique()),
            "label_encoder": label_encoder,
        },
        artifact_path,
    )
    metrics_path.write_text(report, encoding="utf-8")

    return TrainingResult(
        artifact_path=artifact_path,
        metrics_path=metrics_path,
        row_count=len(expanded),
        class_labels=sorted(y.unique()),
    )
