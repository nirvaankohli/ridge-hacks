from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from train.modeling import expand_rows_by_latitude


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the solar storm model using a time-based split.")
    parser.add_argument("--dataset", default="train/datasets/solar_storm_training_data.csv")
    parser.add_argument("--split-ratio", type=float, default=0.8)
    parser.add_argument("--output", default="train/artifacts/solar_storm_time_split_metrics.txt")
    args = parser.parse_args()

    dataset = pd.read_csv(args.dataset)
    dataset["date"] = pd.to_datetime(dataset["date"])
    dataset = dataset.sort_values("date").reset_index(drop=True)

    split_index = max(1, int(len(dataset) * args.split_ratio))
    train_daily = dataset.iloc[:split_index].copy()
    test_daily = dataset.iloc[split_index:].copy()

    train_expanded = expand_rows_by_latitude(train_daily)
    test_expanded = expand_rows_by_latitude(test_daily)

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

    X_train = train_expanded[feature_columns]
    y_train = train_expanded["risk_label"]
    X_test = test_expanded[feature_columns]
    y_test = test_expanded["risk_label"]

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

    predictions_encoded = model.predict(X_test)
    predictions = label_encoder.inverse_transform(predictions_encoded)
    report = classification_report(y_test, predictions, output_dict=False)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"train_days={len(train_daily)}")
    print(f"test_days={len(test_daily)}")
    print(f"train_rows={len(train_expanded)}")
    print(f"test_rows={len(test_expanded)}")
    print(f"metrics={output_path}")


if __name__ == "__main__":
    main()
