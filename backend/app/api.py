
"""

For judges:

- This just serves as a simple API client layer to fetch and aggregate data from various NASA API and NOAA endpoints!
- 

"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


def load_env_value(key: str, env_path: str = "backend/.env") -> str | None:
    value = os.getenv(key)
    if value:
        return value

    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            env_key, env_value = line.split("=", 1)
            if env_key.strip() == key:
                return env_value.strip()
    return None


@dataclass(slots=True)
class SolarWindSnapshot:
    time_tag: str | None
    bz_gsm: float | None
    bt: float | None
    wind_speed: float | None


@dataclass(slots=True)
class KpSnapshot:
    kp: float | None
    observed_time: str | None
    source: str


@dataclass(slots=True)
class ScaleSnapshot:
    g_scale: str | None
    raw: dict[str, Any]


@dataclass(slots=True)
class AuroraSnapshot:
    forecast_time: str | None
    coordinates: list[list[float]]


@dataclass(slots=True)
class CmeImpactSnapshot:
    activity_id: str | None
    estimated_shock_arrival_time: str | None
    speed: float | None
    latitude: float | None
    longitude: float | None


@dataclass(slots=True)
class GstSnapshot:
    gst_id: str | None
    start_time: str | None
    kp_index: float | None


@dataclass(slots=True)
class FlareSnapshot:
    flare_id: str | None
    class_type: str | None
    begin_time: str | None
    peak_time: str | None
    end_time: str | None


class BaseApiClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()


class NasaDonkiClient(BaseApiClient):

    base_url = "https://api.nasa.gov/DONKI"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key or load_env_value("NASA_API_KEY") or "DEMO_KEY"

    async def fetch_cme_analysis(
            
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    
    ) -> list[dict[str, Any]]:
        params = {
            "api_key": self.api_key,
            "mostAccurateOnly": "true",
            "completeEntryOnly": "true",
        }
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return await self._get_json(f"{self.base_url}/CMEAnalysis", params=params)

    async def fetch_gst(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {"api_key": self.api_key}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return await self._get_json(f"{self.base_url}/GST", params=params)

    async def fetch_flares(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {"api_key": self.api_key}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return await self._get_json(f"{self.base_url}/FLR", params=params)

    async def get_next_cme_impact(self) -> CmeImpactSnapshot | None:
        today = datetime.now(UTC).date()
        week_ago = today - timedelta(days=7)
        analyses = await self.fetch_cme_analysis(
            start_date=week_ago.isoformat(),
            end_date=today.isoformat(),
        )

        upcoming: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for item in analyses:
            impact_at = item.get("estimatedShockArrivalTime")
            if not impact_at:
                continue
            try:
                impact_dt = datetime.fromisoformat(impact_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if impact_dt <= now:
                continue
            upcoming.append(item)

        if not upcoming:
            return None

        upcoming.sort(key=lambda item: item["estimatedShockArrivalTime"])
        item = upcoming[0]
        return CmeImpactSnapshot(
            activity_id=item.get("associatedCMEID"),
            estimated_shock_arrival_time=item.get("estimatedShockArrivalTime"),
            speed=_safe_float(item.get("speed")),
            latitude=_safe_float(item.get("latitude")),
            longitude=_safe_float(item.get("longitude")),
        )

    async def get_recent_gst(self) -> list[GstSnapshot]:
        today = datetime.now(UTC).date()
        week_ago = today - timedelta(days=7)
        storms = await self.fetch_gst(week_ago.isoformat(), today.isoformat())

        snapshots: list[GstSnapshot] = []
        for storm in storms:
            kp_samples = storm.get("allKpIndex") or []
            latest_sample = kp_samples[-1] if kp_samples else {}
            snapshots.append(
                GstSnapshot(
                    gst_id=storm.get("gstID"),
                    start_time=storm.get("startTime"),
                    kp_index=_safe_float(latest_sample.get("kpIndex")),
                )
            )
        return snapshots

    async def get_recent_flares(self) -> list[FlareSnapshot]:
        today = datetime.now(UTC).date()
        week_ago = today - timedelta(days=7)
        flares = await self.fetch_flares(week_ago.isoformat(), today.isoformat())
        return [
            FlareSnapshot(
                flare_id=flare.get("flrID"),
                class_type=flare.get("classType"),
                begin_time=flare.get("beginTime"),
                peak_time=flare.get("peakTime"),
                end_time=flare.get("endTime"),
            )
            for flare in flares
        ]


class NoaaClient(BaseApiClient):
    base_url = "https://services.swpc.noaa.gov"

    async def fetch_magnetic_1d(self) -> list[list[Any]]:
        return await self._get_json(f"{self.base_url}/products/solar-wind/mag-1-day.json")

    async def fetch_plasma_1d(self) -> list[list[Any]]:
        return await self._get_json(f"{self.base_url}/products/solar-wind/plasma-1-day.json")

    async def fetch_kp_1m(self) -> list[dict[str, Any]]:
        return await self._get_json(f"{self.base_url}/json/planetary_k_index_1m.json")

    async def fetch_scales(self) -> dict[str, Any]:
        return await self._get_json(f"{self.base_url}/products/noaa-scales.json")

    async def fetch_alerts(self) -> list[Any]:
        return await self._get_json(f"{self.base_url}/products/alerts.json")

    async def fetch_aurora(self) -> dict[str, Any]:
        return await self._get_json(f"{self.base_url}/json/ovation_aurora_latest.json")

    async def get_solar_wind_snapshot(self) -> SolarWindSnapshot:
        mag_data, plasma_data = await self.fetch_magnetic_1d(), await self.fetch_plasma_1d()
        latest_mag = mag_data[-1] if mag_data else []
        latest_plasma = plasma_data[-1] if plasma_data else []
        return SolarWindSnapshot(
            time_tag=_safe_value(latest_mag, 0),
            bz_gsm=_safe_float(_safe_value(latest_mag, 3)),
            bt=_safe_float(_safe_value(latest_mag, 6)),
            wind_speed=_safe_float(_safe_value(latest_plasma, 2)),
        )

    async def get_kp_snapshot(self) -> KpSnapshot:
        data = await self.fetch_kp_1m()
        latest = data[-1] if data else {}
        return KpSnapshot(
            kp=_safe_float(latest.get("kp")),
            observed_time=latest.get("time_tag"),
            source="NOAA 1-minute Kp",
        )

    async def get_scale_snapshot(self) -> ScaleSnapshot:
        data = await self.fetch_scales()
        g_block = data.get("0") or data.get("G") or {}
        scale = g_block.get("Scale") or g_block.get("scale")
        return ScaleSnapshot(g_scale=str(scale) if scale is not None else None, raw=data)

    async def get_alerts(self) -> list[str]:
        data = await self.fetch_alerts()
        return [str(item) for item in data if item]

    async def get_aurora_snapshot(self) -> AuroraSnapshot:
        data = await self.fetch_aurora()
        return AuroraSnapshot(
            forecast_time=data.get("Forecast Time"),
            coordinates=data.get("coordinates", []),
        )


class OpenWeatherClient(BaseApiClient):
    base_url = "https://api.openweathermap.org/data/2.5/forecast"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key or load_env_value("OPENWEATHER_KEY")

    async def fetch_forecast(self, lat: float, lon: float) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENWEATHER_KEY is not configured.")
        params = {"lat": lat, "lon": lon, "appid": self.api_key}
        return await self._get_json(self.base_url, params=params)


class TwilioClient:
    def __init__(self) -> None:
        self.sid = load_env_value("TWILIO_SID")
        self.token = load_env_value("TWILIO_TOKEN")
        self.from_number = load_env_value("TWILIO_FROM")

    def is_configured(self) -> bool:
        return bool(self.sid and self.token and self.from_number)


class SpaceWeatherApi:
    def __init__(
        self,
        nasa: NasaDonkiClient | None = None,
        noaa: NoaaClient | None = None,
        weather: OpenWeatherClient | None = None,
        twilio: TwilioClient | None = None,
    ) -> None:
        self.nasa = nasa or NasaDonkiClient()
        self.noaa = noaa or NoaaClient()
        self.weather = weather or OpenWeatherClient()
        self.twilio = twilio or TwilioClient()

    async def build_summary(self) -> dict[str, Any]:
        solar_wind = await self.noaa.get_solar_wind_snapshot()
        kp = await self.noaa.get_kp_snapshot()
        scales = await self.noaa.get_scale_snapshot()
        alerts = await self.noaa.get_alerts()
        aurora = await self.noaa.get_aurora_snapshot()
        next_cme = await self.nasa.get_next_cme_impact()
        recent_gst = await self.nasa.get_recent_gst()
        recent_flares = await self.nasa.get_recent_flares()

        return {
            "solar_wind": asdict(solar_wind),
            "kp": asdict(kp),
            "scales": asdict(scales),
            "alerts": alerts,
            "aurora": {
                "forecast_time": aurora.forecast_time,
                "point_count": len(aurora.coordinates),
            },
            "next_cme_impact": asdict(next_cme) if next_cme else None,
            "recent_gst": [asdict(item) for item in recent_gst[:5]],
            "recent_flares": [asdict(item) for item in recent_flares[:5]],
            "weather_enabled": bool(self.weather.api_key),
            "twilio_enabled": self.twilio.is_configured(),
        }


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_value(row: list[Any], index: int) -> Any:
    return row[index] if len(row) > index else None
