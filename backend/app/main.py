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


@app.post("/model/predict")
def predict_model(request: ModelPredictionRequest) -> dict:
    return solar_storm_model.predict(request).model_dump()


@app.get("/model/predict/current")
async def predict_current_model(latitude: float = 45.0) -> dict:
    return (await solar_storm_model.predict_current(latitude=latitude)).model_dump()
