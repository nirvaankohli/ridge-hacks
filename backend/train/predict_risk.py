from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict local solar storm risk.")
    parser.add_argument("--artifact", default=Path.cwd() / "train" / "artifacts" / "solar_storm_risk_model.joblib")
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--cme-count-24h", type=float, default=0.0)
    parser.add_argument("--earth-directed-cme-count-72h", type=float, default=0.0)
    parser.add_argument("--max-cme-speed-72h", type=float, default=0.0)
    parser.add_argument("--mean-cme-speed-72h", type=float, default=0.0)
    parser.add_argument("--mean-cme-half-angle-72h", type=float, default=0.0)
    parser.add_argument("--impact-count-24h", type=float, default=0.0)
    parser.add_argument("--flare-count-24h", type=float, default=0.0)
    parser.add_argument("--m-flare-count-72h", type=float, default=0.0)
    parser.add_argument("--x-flare-count-72h", type=float, default=0.0)
    parser.add_argument("--prior-day-max-kp", type=float, default=0.0)
    parser.add_argument("--prior-3day-mean-kp", type=float, default=0.0)
    args = parser.parse_args()

    payload = joblib.load(Path(args.artifact))
    model = payload["model"]
    features = payload["feature_columns"]
    label_encoder = payload["label_encoder"]

    frame = pd.DataFrame(
        [
            {
                "latitude": args.latitude,
                "latitude_abs": abs(args.latitude),
                "cme_count_24h": args.cme_count_24h,
                "earth_directed_cme_count_72h": args.earth_directed_cme_count_72h,
                "max_cme_speed_72h": args.max_cme_speed_72h,
                "mean_cme_speed_72h": args.mean_cme_speed_72h,
                "mean_cme_half_angle_72h": args.mean_cme_half_angle_72h,
                "impact_count_24h": args.impact_count_24h,
                "flare_count_24h": args.flare_count_24h,
                "m_flare_count_72h": args.m_flare_count_72h,
                "x_flare_count_72h": args.x_flare_count_72h,
                "prior_day_max_kp": args.prior_day_max_kp,
                "prior_3day_mean_kp": args.prior_3day_mean_kp,
            }
        ]
    )

    prediction_encoded = model.predict(frame[features])[0]
    prediction = label_encoder.inverse_transform([prediction_encoded])[0]
    probabilities = model.predict_proba(frame[features])[0]

    print(f"prediction={prediction}")
    for encoded_label, probability in zip(model.classes_, probabilities, strict=True):
        label = label_encoder.inverse_transform([encoded_label])[0]
        print(f"{label}={probability:.4f}")


if __name__ == "__main__":
    main()
