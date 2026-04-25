from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from pydantic import BaseModel, Field

from app.api import NasaDonkiClient, NoaaClient


class ModelPredictionRequest(BaseModel):
    date: str | None = None
    latitude: float = 45.0
    cme_count_24h: float | None = None
    earth_directed_cme_count_72h: float | None = None
    max_cme_speed_72h: float | None = None
    mean_cme_speed_72h: float | None = None
    mean_cme_half_angle_72h: float | None = None
    impact_count_24h: float | None = None
    flare_count_24h: float | None = None
    m_flare_count_72h: float | None = None
    x_flare_count_72h: float | None = None
    prior_day_max_kp: float | None = None
    prior_3day_mean_kp: float | None = None


class ModelPredictionResponse(BaseModel):
    prediction: str
    confidence: float
    probabilities: dict[str, float]
    features_used: dict[str, float]
    top_factors: list[dict[str, str | float]]
    explanation: str
    forecast_window: str = "next 24-72 hours"
    source: str = Field(description="Whether the prediction came from a dataset date row or raw request data.")


@dataclass(slots=True)
class LoadedModel:
    model: Any
    feature_columns: list[str]
    label_encoder: Any


class ReplayPredictionItem(BaseModel):
    date: str
    latitude: float
    prediction: str
    confidence: float
    probabilities: dict[str, float]
    explanation: str


class SolarStormModelWrapper:
    def __init__(
        self,
        artifact_path: str | Path = "backend/train/artifacts/solar_storm_risk_model.joblib",
        dataset_path: str | Path = "backend/train/datasets/solar_storm_training_data.csv",
    ) -> None:
        self.artifact_path = Path(artifact_path)
        self.dataset_path = Path(dataset_path)
        self._loaded_model: LoadedModel | None = None
        self._nasa = NasaDonkiClient()
        self._noaa = NoaaClient()

    def predict(self, request: ModelPredictionRequest) -> ModelPredictionResponse:
        loaded = self._get_loaded_model()
        feature_map, source = self._build_feature_map(request, loaded.feature_columns)
        frame = pd.DataFrame([feature_map])

        prediction_encoded = loaded.model.predict(frame[loaded.feature_columns])[0]
        prediction = loaded.label_encoder.inverse_transform([prediction_encoded])[0]
        probability_values = loaded.model.predict_proba(frame[loaded.feature_columns])[0]

        probabilities: dict[str, float] = {}
        for encoded_label, probability in zip(loaded.model.classes_, probability_values, strict=True):
            label = loaded.label_encoder.inverse_transform([encoded_label])[0]
            probabilities[label] = float(probability)

        return self._build_response(prediction, probabilities, feature_map, source)

    async def predict_current(self, latitude: float = 45.0) -> ModelPredictionResponse:
        today = datetime.now(UTC).date()
        week_ago = today - timedelta(days=7)
        three_days_ago = today - timedelta(days=3)
        day_ago = today - timedelta(days=1)

        cme_analysis = await self._safe_fetch(
            self._nasa.fetch_cme_analysis, week_ago.isoformat(), today.isoformat()
        )
        flares = await self._safe_fetch(
            self._nasa.fetch_flares, week_ago.isoformat(), today.isoformat()
        )
        gst = await self._safe_fetch(
            self._nasa.fetch_gst, week_ago.isoformat(), today.isoformat()
        )
        kp_snapshot = await self._noaa.get_kp_snapshot()

        now = datetime.now(UTC)
        cme_rows = [_normalize_cme_row(item) for item in cme_analysis]
        flare_rows = [_normalize_flare_row(item) for item in flares]
        daily_kp = _build_daily_kp_labels(gst)

        last_24h_cmes = [row for row in cme_rows if row["start_time"] and row["start_time"] >= datetime.combine(day_ago, datetime.min.time(), tzinfo=UTC)]
        last_72h_cmes = [row for row in cme_rows if row["start_time"] and row["start_time"] >= datetime.combine(three_days_ago, datetime.min.time(), tzinfo=UTC)]
        earth_directed_72h = [
            row for row in last_72h_cmes if abs(row["longitude"]) <= 45.0 and abs(row["latitude"]) <= 30.0
        ]
        next_24h_impacts = [
            row for row in cme_rows
            if row["impact_time"] and now <= row["impact_time"] <= now + timedelta(days=1)
        ]

        last_24h_flares = [row for row in flare_rows if row["begin_time"] and row["begin_time"] >= datetime.combine(day_ago, datetime.min.time(), tzinfo=UTC)]
        last_72h_flares = [row for row in flare_rows if row["begin_time"] and row["begin_time"] >= datetime.combine(three_days_ago, datetime.min.time(), tzinfo=UTC)]

        request = ModelPredictionRequest(
            latitude=latitude,
            cme_count_24h=float(len(last_24h_cmes)),
            earth_directed_cme_count_72h=float(len(earth_directed_72h)),
            max_cme_speed_72h=max((row["speed"] for row in last_72h_cmes), default=0.0),
            mean_cme_speed_72h=_safe_mean([row["speed"] for row in last_72h_cmes]),
            mean_cme_half_angle_72h=_safe_mean([row["half_angle"] for row in last_72h_cmes]),
            impact_count_24h=float(len(next_24h_impacts)),
            flare_count_24h=float(len(last_24h_flares)),
            m_flare_count_72h=float(sum(1 for row in last_72h_flares if row["class_type"].startswith("M"))),
            x_flare_count_72h=float(sum(1 for row in last_72h_flares if row["class_type"].startswith("X"))),
            prior_day_max_kp=daily_kp.get(day_ago.isoformat(), kp_snapshot.kp or 0.0),
            prior_3day_mean_kp=_safe_mean(
                [
                    daily_kp.get((today - timedelta(days=offset)).isoformat(), 0.0)
                    for offset in range(1, 4)
                ]
            ),
        )
        result = self.predict(request)
        result.source = "live_space_weather"
        return result

    def predict_range(self, start_date: str, end_date: str, latitude: float = 45.0) -> list[ReplayPredictionItem]:
        dataset_path = self._resolve_path(self.dataset_path)
        if not dataset_path.exists():
            return []

        dataset = pd.read_csv(dataset_path)
        matched = dataset[(dataset["date"] >= start_date) & (dataset["date"] <= end_date)].sort_values("date")

        items: list[ReplayPredictionItem] = []
        for date_value in matched["date"].tolist():
            result = self.predict(ModelPredictionRequest(date=str(date_value), latitude=latitude))
            items.append(
                ReplayPredictionItem(
                    date=str(date_value),
                    latitude=latitude,
                    prediction=result.prediction,
                    confidence=result.confidence,
                    probabilities=result.probabilities,
                    explanation=result.explanation,
                )
            )
        return items

    async def _safe_fetch(self, fetcher, *args: Any) -> list[dict[str, Any]]:
        try:
            return await fetcher(*args)
        except Exception:
            return []

    def _get_loaded_model(self) -> LoadedModel:
        if self._loaded_model is not None:
            return self._loaded_model

        payload = joblib.load(self._resolve_path(self.artifact_path))
        self._loaded_model = LoadedModel(
            model=payload["model"],
            feature_columns=list(payload["feature_columns"]),
            label_encoder=payload["label_encoder"],
        )
        return self._loaded_model

    def _build_feature_map(
        self,
        request: ModelPredictionRequest,
        feature_columns: list[str],
    ) -> tuple[dict[str, float], str]:
        base_map = self._get_date_features(request.date) if request.date else {}
        source = "dataset_date" if base_map else "raw_request"

        raw_map = request.model_dump(exclude_none=True)
        raw_map.pop("date", None)
        raw_map["latitude_abs"] = abs(raw_map.get("latitude", request.latitude))

        feature_map: dict[str, float] = {}
        for feature in feature_columns:
            if feature in raw_map:
                feature_map[feature] = float(raw_map[feature])
            elif feature in base_map:
                feature_map[feature] = float(base_map[feature])
            elif feature == "latitude_abs":
                feature_map[feature] = abs(float(raw_map.get("latitude", request.latitude)))
            elif feature == "latitude":
                feature_map[feature] = float(raw_map.get("latitude", request.latitude))
            else:
                feature_map[feature] = 0.0

        return feature_map, source

    def _get_date_features(self, date_value: str | None) -> dict[str, float]:
        if not date_value:
            return {}
        dataset_path = self._resolve_path(self.dataset_path)
        if not dataset_path.exists():
            return {}

        dataset = pd.read_csv(dataset_path)
        matched = dataset[dataset["date"] == date_value]
        if matched.empty:
            return {}

        row = matched.iloc[0].to_dict()
        row.pop("date", None)
        row.pop("target_kp", None)
        return {key: float(value) for key, value in row.items()}

    def _build_response(
        self,
        prediction: str,
        probabilities: dict[str, float],
        feature_map: dict[str, float],
        source: str,
    ) -> ModelPredictionResponse:
        confidence = max(probabilities.values()) if probabilities else 0.0
        top_factors = self._get_top_factors(feature_map)
        explanation = self._build_explanation(prediction, top_factors)
        return ModelPredictionResponse(
            prediction=prediction,
            confidence=float(confidence),
            probabilities=probabilities,
            features_used=feature_map,
            top_factors=top_factors,
            explanation=explanation,
            source=source,
        )

    def _get_top_factors(self, feature_map: dict[str, float]) -> list[dict[str, str | float]]:
        factor_labels = {
            "earth_directed_cme_count_72h": "Earth-directed CME count",
            "max_cme_speed_72h": "Max CME speed",
            "impact_count_24h": "Predicted impact count",
            "x_flare_count_72h": "X-class flare count",
            "m_flare_count_72h": "M-class flare count",
            "flare_count_24h": "Recent flare count",
            "prior_day_max_kp": "Previous day Kp",
            "prior_3day_mean_kp": "3-day Kp average",
            "cme_count_24h": "Recent CME count",
        }
        ranked_keys = sorted(
            factor_labels,
            key=lambda key: abs(feature_map.get(key, 0.0)),
            reverse=True,
        )
        factors: list[dict[str, str | float]] = []
        for key in ranked_keys:
            value = float(feature_map.get(key, 0.0))
            if value <= 0:
                continue
            factors.append({"feature": factor_labels[key], "value": value, "key": key})
            if len(factors) == 3:
                break
        return factors

    def _build_explanation(self, prediction: str, top_factors: list[dict[str, str | float]]) -> str:
        if not top_factors:
            return f"The model sees {prediction} risk for the next 24-72 hours with limited storm-driving signals."
        factor_text = ", ".join(str(item["feature"]) for item in top_factors[:3])
        return f"The model predicts {prediction} risk in the next 24-72 hours mainly because of {factor_text}."

    def _resolve_path(self, path: Path) -> Path:
        if path.exists():
            return path
        backend_root = Path(__file__).resolve().parents[1]
        fallback = backend_root / path.name if path.parent == Path(".") else backend_root / path.relative_to("backend")
        return fallback if fallback.exists() else path


def _build_daily_kp_labels(storms: list[dict[str, Any]]) -> dict[str, float]:
    daily_max: dict[str, float] = {}
    for storm in storms:
        for sample in storm.get("allKpIndex") or []:
            observed_time = sample.get("observedTime")
            kp = _safe_float(sample.get("kpIndex"))
            if not observed_time or kp is None:
                continue
            day = observed_time[:10]
            daily_max[day] = max(kp, daily_max.get(day, 0.0))
    return daily_max


def _normalize_cme_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_time": _to_datetime(item.get("time21_5")),
        "impact_time": _to_datetime(item.get("estimatedShockArrivalTime")),
        "speed": _safe_float(item.get("speed")) or 0.0,
        "half_angle": _safe_float(item.get("halfAngle")) or 0.0,
        "latitude": _safe_float(item.get("latitude")) or 0.0,
        "longitude": _safe_float(item.get("longitude")) or 0.0,
    }


def _normalize_flare_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "begin_time": _to_datetime(item.get("beginTime")),
        "class_type": str(item.get("classType") or ""),
    }


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_mean(values: list[float]) -> float:
    filtered = [value for value in values if value is not None]
    return float(sum(filtered) / len(filtered)) if filtered else 0.0
