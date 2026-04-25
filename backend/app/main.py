from fastapi import FastAPI

from app.api import SpaceWeatherApi

app = FastAPI()
space_weather_api = SpaceWeatherApi()


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "ridge-hacks backend is running"}


@app.get("/space-weather")
async def read_space_weather() -> dict:
    return await space_weather_api.build_summary()
