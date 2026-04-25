"""

For judges:

- FAST API backend

"""

from fastapi import FastAPI

from app.api import SpaceWeatherApi
from app.model import ModelPredictionRequest, SolarStormModelWrapper

app = FastAPI()
space_weather_api = SpaceWeatherApi()
solar_storm_model = SolarStormModelWrapper()


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "ridge-hacks backend is running"}


@app.get("/space-weather")
async def read_space_weather() -> dict:
    return await space_weather_api.build_summary()


@app.get("/api/health")
async def read_health() -> dict:
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
