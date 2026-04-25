"""

For judges:

- FAST API backend

"""

import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import HTTPException

from app.api import SpaceWeatherApi
from app.briefing import BriefingContext, CivilianBriefingService
from app.core.scheduler import start_scheduler, stop_scheduler, warm_scheduler
from app.core.subscribers import (
    create_or_update_subscriber,
    delete_subscriber,
    init_subscribers_db,
    list_subscribers,
    mask_phone,
)
from app.model import ModelPredictionRequest, SolarStormModelWrapper

space_weather_api = SpaceWeatherApi()
solar_storm_model = SolarStormModelWrapper()
civilian_briefing_service = CivilianBriefingService()


class AlertSubscriptionRequest(BaseModel):
    phone: str
    lat: float
    lon: float
    kp_threshold: float


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_subscribers_db()
    await warm_scheduler(space_weather_api)
    start_scheduler(space_weather_api)
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "ridge-hacks backend is running"}


@app.get("/space-weather")
async def read_space_weather() -> dict:
    return await space_weather_api.build_summary()


@app.get("/api/health")
async def read_health() -> dict:
    return await space_weather_api.build_health()


@app.get("/health")
async def read_health_alias() -> dict:
    return await space_weather_api.build_health()


@app.get("/api/status")
async def read_status() -> dict:
    return await space_weather_api.build_status()


@app.get("/api/aurora")
async def read_aurora() -> dict:
    return await space_weather_api.build_aurora()


@app.get("/api/visibility")
async def read_visibility(lat: float, lon: float) -> dict:
    return await space_weather_api.build_visibility(lat=lat, lon=lon)


@app.get("/api/infrastructure")
async def read_infrastructure() -> dict:
    return await space_weather_api.build_infrastructure()


@app.get("/api/civilian-brief")
async def read_civilian_brief(latitude: float = 45.0, longitude: float = -74.0, analysis_date: str | None = None) -> dict:
    status = await space_weather_api.build_status()
    visibility = await space_weather_api.build_visibility(lat=latitude, lon=longitude)
    aurora = await space_weather_api.build_aurora()
    infrastructure = await space_weather_api.build_infrastructure()
    today_iso = datetime.now(UTC).date().isoformat()
    if analysis_date and analysis_date != today_iso:
        model = solar_storm_model.predict(ModelPredictionRequest(date=analysis_date, latitude=latitude))
    else:
        model = await solar_storm_model.predict_current(latitude=latitude)

    brief = await civilian_briefing_service.build(
        BriefingContext(
            analysis_date=analysis_date or "live",
            latitude=latitude,
            model_prediction=model.prediction,
            model_confidence=model.confidence,
            status=status,
            visibility=visibility,
            aurora=aurora,
            infrastructure=infrastructure,
        )
    )
    return brief.model_dump()


@app.post("/api/alerts/subscribe")
def subscribe_alerts(request: AlertSubscriptionRequest) -> dict:
    phone = _normalize_phone(request.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phone number.")
    if not 1 <= request.kp_threshold <= 9:
        raise HTTPException(status_code=400, detail="kp_threshold must be between 1 and 9.")
    record = create_or_update_subscriber(phone, request.lat, request.lon, request.kp_threshold)
    return {
        "id": record["id"],
        "phone_masked": mask_phone(record["phone"]),
        "lat": record["lat"],
        "lon": record["lon"],
        "kp_threshold": record["kp_threshold"],
        "created_at": record["created_at"],
    }


@app.get("/api/alerts/subscribers")
def read_subscribers() -> dict:
    return {
        "items": [
            {
                "id": item["id"],
                "phone_masked": mask_phone(item["phone"]),
                "lat": item["lat"],
                "lon": item["lon"],
                "kp_threshold": item["kp_threshold"],
                "created_at": item["created_at"],
            }
            for item in list_subscribers()
        ]
    }


@app.delete("/api/alerts/subscribers/{subscriber_id}")
def remove_subscriber(subscriber_id: str) -> dict:
    if not delete_subscriber(subscriber_id):
        raise HTTPException(status_code=404, detail="Subscriber not found.")
    return {"deleted": True, "id": subscriber_id}


@app.post("/model/predict")
def predict_model(request: ModelPredictionRequest) -> dict:
    return solar_storm_model.predict(request).model_dump()


@app.get("/model/predict/current")
async def predict_current_model(latitude: float = 45.0) -> dict:
    return (await solar_storm_model.predict_current(latitude=latitude)).model_dump()


@app.get("/model/predict/location")
async def predict_location_model(latitude: float) -> dict:
    return (await solar_storm_model.predict_current(latitude=latitude)).model_dump()


@app.get("/model/replay")
def replay_model(start_date: str, end_date: str, latitude: float = 45.0) -> dict:
    return {
        "forecast_window": "next 24-72 hours",
        "latitude": latitude,
        "items": [item.model_dump() for item in solar_storm_model.predict_range(start_date, end_date, latitude)],
    }


def _normalize_phone(phone: str) -> str | None:
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10 or len(digits) > 15:
        return None
    return f"+{digits}"
