
"""

For judges:

- This just serves as a simple API client layer to fetch and aggregate data from various NASA API and NOAA endpoints!
- Pretty redundant code, but it's clean and works well for our needs. We can easily swap out the data sources or add new ones as needed.

"""

from __future__ import annotations

import asyncio
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.core.cache import SpaceWeatherCache, space_weather_cache
from app.core.scheduler import is_scheduler_running


def load_env_value(key: str, env_path: str = "backend/.env") -> str | None:
    value = os.getenv(key)
    if value:
        return value

    candidate_paths = [
        Path(env_path),
        Path(".env"),
        Path(__file__).resolve().parents[1] / ".env",
    ]

    for candidate in candidate_paths:
        if not candidate.exists():
            continue
        with open(candidate, "r", encoding="utf-8") as env_file:
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
    def __init__(self, timeout: float = 60.0) -> None:
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
        cache: SpaceWeatherCache | None = None,
    ) -> None:
        self.nasa = nasa or NasaDonkiClient()
        self.noaa = noaa or NoaaClient()
        self.weather = weather or OpenWeatherClient()
        self.twilio = twilio or TwilioClient()
        self.cache = cache or space_weather_cache

    async def build_summary(self) -> dict[str, Any]:
        snapshot = await self._ensure_snapshot()
        realtime = snapshot.get("realtime", {})
        aurora = snapshot.get("aurora", {})
        donki = snapshot.get("donki", {})

        return {
            "solar_wind": {
                "time_tag": realtime.get("solar_wind_time_tag"),
                "bz_gsm": realtime.get("bz"),
                "bt": realtime.get("bt"),
                "wind_speed": realtime.get("wind_speed"),
            },
            "kp": {
                "kp": realtime.get("kp"),
                "observed_time": realtime.get("kp_observed_time"),
                "source": realtime.get("kp_source", "NOAA 1-minute Kp"),
            },
            "scales": {"g_scale": realtime.get("g_scale"), "raw": realtime.get("scales_raw", {})},
            "alerts": realtime.get("alerts", []),
            "aurora": {
                "forecast_time": aurora.get("forecast_time"),
                "point_count": len(aurora.get("coordinates", [])),
            },
            "next_cme_impact": donki.get("next_cme_impact"),
            "recent_gst": donki.get("recent_gst", [])[:5],
            "recent_flares": donki.get("recent_flares", [])[:5],
            "weather_enabled": bool(self.weather.api_key),
            "twilio_enabled": self.twilio.is_configured(),
        }

    async def build_health(self) -> dict[str, Any]:
        snapshot = await self._ensure_snapshot()
        return {
            "status": "ok",
            "scheduler_running": is_scheduler_running(),
            "sources": {
                "nasa_configured": bool(self.nasa.api_key),
                "weather_enabled": bool(self.weather.api_key),
                "twilio_enabled": self.twilio.is_configured(),
            },
            "source_freshness": _build_source_freshness(snapshot),
            "source_errors": snapshot.get("source_errors", {}),
            "checked_at": datetime.now(UTC).isoformat(),
        }

    async def build_status(self) -> dict[str, Any]:
        snapshot = await self._ensure_snapshot()
        realtime = snapshot.get("realtime", {})
        donki = snapshot.get("donki", {})
        cme_impact = (donki.get("next_cme_impact") or {}).get("estimated_shock_arrival_time")

        return {
            "kp": realtime.get("kp"),
            "kp_source": realtime.get("kp_source", "NOAA 1-minute Kp"),
            "bz": realtime.get("bz"),
            "bt": realtime.get("bt"),
            "wind_speed": realtime.get("wind_speed"),
            "g_scale": realtime.get("g_scale"),
            "storm_severity": _get_storm_severity(realtime.get("kp"), realtime.get("bz")),
            "alerts": realtime.get("alerts", []),
            "cme_impact": cme_impact,
            "cme_countdown_seconds": _countdown_seconds(cme_impact),
            "last_updated": snapshot.get("last_updated"),
            "stale": _is_stale(snapshot.get("source_timestamps", {}).get("realtime"), 10),
            "source_errors": snapshot.get("source_errors", {}),
        }

    async def build_aurora(self) -> dict[str, Any]:
        snapshot = await self._ensure_snapshot()
        realtime = snapshot.get("realtime", {})
        aurora = snapshot.get("aurora", {})
        current_kp = realtime.get("kp") or 0.0
        return {
            "kp": current_kp,
            "viewline_latitude": _get_viewline_latitude(current_kp),
            "aurora": {
                "forecast_time": aurora.get("forecast_time"),
                "coordinates": aurora.get("coordinates", []),
                "point_count": len(aurora.get("coordinates", [])),
            },
            "last_updated": aurora.get("forecast_time") or snapshot.get("last_updated"),
            "stale": _is_stale(snapshot.get("source_timestamps", {}).get("aurora"), 15),
            "source_errors": snapshot.get("source_errors", {}),
        }

    async def build_visibility(self, lat: float, lon: float) -> dict[str, Any]:
        snapshot = await self._ensure_snapshot()
        current_kp = snapshot.get("realtime", {}).get("kp") or 0.0
        kp_required = _get_kp_required_for_latitude(lat)
        probability = _get_visibility_probability(current_kp, lat)

        cloud_cover_percent = None
        adjusted_probability = probability
        if self.weather.api_key:
            try:
                forecast = await self.weather.fetch_forecast(lat, lon)
                cloud_cover_percent = _extract_cloud_cover_percent(forecast)
                if cloud_cover_percent is not None:
                    adjusted_probability = _adjust_for_cloud_cover(probability, cloud_cover_percent)
            except Exception:
                cloud_cover_percent = None

        final_probability = adjusted_probability if adjusted_probability is not None else probability
        return {
            "latitude": lat,
            "longitude": lon,
            "current_kp": current_kp,
            "kp_required": round(kp_required, 2),
            "probability": probability,
            "viewline_latitude": _get_viewline_latitude(current_kp),
            "cloud_cover_percent": cloud_cover_percent,
            "adjusted_probability": adjusted_probability,
            "message": _build_visibility_message(final_probability),
        }

    async def build_infrastructure(self) -> dict[str, Any]:
        snapshot = await self._ensure_snapshot()
        realtime = snapshot.get("realtime", {})
        current_kp = realtime.get("kp") or 0.0
        return {
            "current_kp": current_kp,
            "current_g_scale": realtime.get("g_scale"),
            "region_risks": _get_all_region_risks(current_kp),
            "gps_band_start_lat": max(0.0, _get_viewline_latitude(current_kp) + 5.0),
            "recommended_warning_level": _get_storm_severity(current_kp, None)["level"],
            "stale": _is_stale(snapshot.get("source_timestamps", {}).get("realtime"), 10),
            "source_errors": snapshot.get("source_errors", {}),
        }

    async def warm_cache(self) -> None:
        await asyncio.gather(
            self.poll_realtime_space_weather(),
            self.poll_aurora_feed(),
            self.poll_donki_data(),
        )

    async def poll_realtime_space_weather(self) -> None:
        solar_wind_task = self.noaa.get_solar_wind_snapshot()
        kp_task = self.noaa.get_kp_snapshot()
        scales_task = self.noaa.get_scale_snapshot()
        alerts_task = self.noaa.get_alerts()
        solar_wind, kp, scales, alerts = await asyncio.gather(
            solar_wind_task,
            kp_task,
            scales_task,
            alerts_task,
            return_exceptions=True,
        )

        previous = (await self.cache.get_snapshot()).get("realtime", {})
        payload = dict(previous)

        if isinstance(solar_wind, Exception):
            await self.cache.mark_error("solar_wind", str(solar_wind))
        else:
            payload.update(
                {
                    "solar_wind_time_tag": solar_wind.time_tag,
                    "bz": solar_wind.bz_gsm,
                    "bt": solar_wind.bt,
                    "wind_speed": solar_wind.wind_speed,
                }
            )
            await self.cache.clear_error("solar_wind")

        if isinstance(kp, Exception):
            await self.cache.mark_error("kp", str(kp))
        else:
            payload.update(
                {
                    "kp": kp.kp,
                    "kp_observed_time": kp.observed_time,
                    "kp_source": kp.source,
                }
            )
            await self.cache.clear_error("kp")

        if isinstance(scales, Exception):
            await self.cache.mark_error("scales", str(scales))
        else:
            payload.update({"g_scale": scales.g_scale, "scales_raw": scales.raw})
            await self.cache.clear_error("scales")

        if isinstance(alerts, Exception):
            await self.cache.mark_error("alerts", str(alerts))
        else:
            payload["alerts"] = alerts
            await self.cache.clear_error("alerts")

        await self.cache.update_realtime(payload)

    async def poll_aurora_feed(self) -> None:
        previous = (await self.cache.get_snapshot()).get("aurora", {})
        try:
            aurora = await self.noaa.get_aurora_snapshot()
            await self.cache.update_aurora(
                {
                    **previous,
                    "forecast_time": aurora.forecast_time,
                    "coordinates": aurora.coordinates,
                }
            )
            await self.cache.clear_error("aurora")
        except Exception as exc:
            await self.cache.mark_error("aurora", str(exc))

    async def poll_donki_data(self) -> None:
        next_cme_task = self.nasa.get_next_cme_impact()
        recent_gst_task = self.nasa.get_recent_gst()
        recent_flares_task = self.nasa.get_recent_flares()
        next_cme, recent_gst, recent_flares = await asyncio.gather(
            next_cme_task,
            recent_gst_task,
            recent_flares_task,
            return_exceptions=True,
        )

        previous = (await self.cache.get_snapshot()).get("donki", {})
        payload = dict(previous)

        if isinstance(next_cme, Exception):
            await self.cache.mark_error("donki_cme", str(next_cme))
        else:
            payload["next_cme_impact"] = asdict(next_cme) if next_cme else None
            await self.cache.clear_error("donki_cme")

        if isinstance(recent_gst, Exception):
            await self.cache.mark_error("donki_gst", str(recent_gst))
        else:
            payload["recent_gst"] = [asdict(item) for item in recent_gst[:5]]
            await self.cache.clear_error("donki_gst")

        if isinstance(recent_flares, Exception):
            await self.cache.mark_error("donki_flares", str(recent_flares))
        else:
            payload["recent_flares"] = [asdict(item) for item in recent_flares[:5]]
            await self.cache.clear_error("donki_flares")

        await self.cache.update_donki(payload)

    async def _ensure_snapshot(self) -> dict[str, Any]:
        snapshot = await self.cache.get_snapshot()
        if snapshot.get("last_updated"):
            return snapshot
        await self.warm_cache()
        return await self.cache.get_snapshot()


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_value(row: list[Any], index: int) -> Any:
    return row[index] if len(row) > index else None


def _safe_int(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _latest_time_tag(*values: str | None) -> str | None:
    timestamps: list[datetime] = []
    for value in values:
        if not value:
            continue
        try:
            timestamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            continue
    if not timestamps:
        return None
    return max(timestamps).isoformat()


def _countdown_seconds(value: str | None) -> int | None:
    if not value:
        return None
    try:
        target = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((target - datetime.now(UTC)).total_seconds()))


def _is_stale(value: str | None, max_age_minutes: int) -> bool:
    if not value:
        return True
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    return (datetime.now(UTC) - timestamp) > timedelta(minutes=max_age_minutes)


def _get_storm_severity(kp: float | None, bz: float | None) -> dict[str, str]:
    kp = kp or 0.0
    if kp >= 8 or (bz is not None and bz < -15):
        return {"level": "SEVERE", "color": "#CC0000", "label": "G4-G5 Major Storm"}
    if kp >= 6 or (bz is not None and bz < -10):
        return {"level": "MODERATE", "color": "#E87722", "label": "G2-G3 Storm"}
    if kp >= 5 or (bz is not None and bz < -5):
        return {"level": "MINOR", "color": "#E8C422", "label": "G1 Minor Storm"}
    return {"level": "QUIET", "color": "#2E8B57", "label": "Quiet Conditions"}


def _get_viewline_latitude(kp: float) -> float:
    return max(40.0, 67.0 - kp * 2.5)


def _get_kp_required_for_latitude(latitude: float) -> float:
    return (90.0 - abs(latitude)) / 7.5


def _get_visibility_probability(current_kp: float, latitude: float) -> int:
    kp_required = _get_kp_required_for_latitude(latitude)
    probability = min(100.0, max(0.0, ((current_kp - kp_required) / 3.0) * 100.0))
    return round(probability)


def _adjust_for_cloud_cover(probability: int, cloud_cover: int) -> int:
    if cloud_cover <= 20:
        return probability
    if cloud_cover <= 50:
        return round(probability * 0.8)
    if cloud_cover <= 80:
        return round(probability * 0.5)
    return round(probability * 0.2)


def _extract_cloud_cover_percent(forecast: dict[str, Any]) -> int | None:
    items = forecast.get("list") or []
    if not items:
        return None
    clouds = items[0].get("clouds") or {}
    return _safe_int(clouds.get("all"))


def _build_visibility_message(probability: int) -> str:
    if probability >= 70:
        return "Strong chance if skies stay clear."
    if probability >= 35:
        return "Possible under dark, clear skies."
    return "Aurora unlikely from this location right now."


def _get_all_region_risks(kp: float) -> list[dict[str, Any]]:
    regions = [
        ("NPCC", "Northeast Power Coordinating Council", 5.0),
        ("RFC", "ReliabilityFirst", 5.0),
        ("SERC", "SERC Reliability", 6.0),
        ("MRO", "Midwest Reliability Organization", 5.0),
        ("WECC", "Western Electricity Coordinating Council", 5.0),
        ("TRE", "Texas Reliability Entity", 7.0),
    ]
    return [
        {
            "region_id": region_id,
            "name": name,
            "threshold": threshold,
            "threat_level": _get_region_threat_level(kp, threshold)["level"],
            "color": _get_region_threat_level(kp, threshold)["color"],
        }
        for region_id, name, threshold in regions
    ]


def _get_region_threat_level(kp: float, threshold: float) -> dict[str, str]:
    if kp < threshold:
        return {"level": "none", "color": "#2E8B57"}
    if kp < threshold + 1:
        return {"level": "minor", "color": "#E8C422"}
    if kp < threshold + 2:
        return {"level": "moderate", "color": "#E87722"}
    return {"level": "severe", "color": "#CC0000"}


def _build_source_freshness(snapshot: dict[str, Any]) -> dict[str, Any]:
    source_timestamps = snapshot.get("source_timestamps", {})
    return {
        source: {
            "last_updated": timestamp,
            "stale": _is_stale(timestamp, 15 if source == "aurora" else 20),
        }
        for source, timestamp in source_timestamps.items()
    }
