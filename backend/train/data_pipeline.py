from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from app.api import NasaDonkiClient, _safe_float


@dataclass(slots=True)
class HistoricalDataBundle:
    cme_analysis: list[dict[str, Any]]
    gst: list[dict[str, Any]]
    flares: list[dict[str, Any]]


class HistoricalDatasetBuilder:
    def __init__(self, nasa_client: NasaDonkiClient | None = None) -> None:
        self.nasa_client = nasa_client or NasaDonkiClient()
        self.cache_dir = Path("train/cache")

    async def fetch_bundle(self, start_date: str, end_date: str) -> HistoricalDataBundle:
        cme_analysis = await self._fetch_chunked(self.nasa_client.fetch_cme_analysis, start_date, end_date)
        gst = await self._fetch_chunked(self.nasa_client.fetch_gst, start_date, end_date)
        flares = await self._fetch_chunked(self.nasa_client.fetch_flares, start_date, end_date)
        return HistoricalDataBundle(
            cme_analysis=self._dedupe_records(cme_analysis),
            gst=self._dedupe_records(gst),
            flares=self._dedupe_records(flares),
        )

    def build_dataset(self, bundle: HistoricalDataBundle, start_date: str, end_date: str) -> pd.DataFrame:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        daily_kp = self._build_daily_kp_labels(bundle.gst)
        cme_frame = self._build_cme_frame(bundle.cme_analysis)
        flare_frame = self._build_flare_frame(bundle.flares)

        rows: list[dict[str, Any]] = []
        current = start
        while current <= end:
            rows.append(
                {
                    "date": current.isoformat(),
                    **self._aggregate_cme_features(cme_frame, current),
                    **self._aggregate_flare_features(flare_frame, current),
                    "prior_day_max_kp": daily_kp.get((current - timedelta(days=1)).isoformat(), 0.0),
                    "prior_3day_mean_kp": self._mean_prior_kp(daily_kp, current, window_days=3),
                    "target_kp": daily_kp.get(current.isoformat(), 0.0),
                }
            )
            current += timedelta(days=1)

        return pd.DataFrame(rows).fillna(0.0)

    def persist_dataset(self, frame: pd.DataFrame, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)

    def _build_daily_kp_labels(self, storms: list[dict[str, Any]]) -> dict[str, float]:
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

    async def _fetch_chunked(self, fetcher, start_date: str, end_date: str) -> list[dict[str, Any]]:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        current = start
        records: list[dict[str, Any]] = []
        endpoint_name = fetcher.__name__

        while current <= end:
            chunk_end = min(current + timedelta(days=89), end)
            cache_path = self._get_cache_path(endpoint_name, current, chunk_end)
            if cache_path.exists():
                records.extend(json.loads(cache_path.read_text(encoding="utf-8")))
            else:
                chunk_records = await self._fetch_with_retry(fetcher, current, chunk_end)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(chunk_records), encoding="utf-8")
                records.extend(chunk_records)
            current = chunk_end + timedelta(days=1)
        return records

    async def _fetch_with_retry(self, fetcher, start: date, end: date, attempts: int = 3) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return await fetcher(start.isoformat(), end.isoformat())
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in {429, 502, 503, 504}:
                    raise
            except httpx.TimeoutException as exc:
                last_error = exc
            await asyncio.sleep(attempt + 1)

        try:
            return await fetcher(start.isoformat(), end.isoformat())
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {429, 502, 503, 504}:
                raise
            last_error = exc
        except httpx.TimeoutException:
            pass

        span_days = (end - start).days + 1
        if span_days <= 30:
            print(f"warning: skipping {start.isoformat()} to {end.isoformat()} after retries: {last_error}")
            return []

        midpoint = start + timedelta(days=(span_days // 2) - 1)
        left = await self._fetch_with_retry(fetcher, start, midpoint)
        right = await self._fetch_with_retry(fetcher, midpoint + timedelta(days=1), end)
        return left + right

    def _get_cache_path(self, endpoint_name: str, start: date, end: date) -> Path:
        return self.cache_dir / f"{endpoint_name}_{start.isoformat()}_{end.isoformat()}.json"

    def _dedupe_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for record in records:
            key = str(sorted(record.items()))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        return deduped

    def _build_cme_frame(self, cmes: list[dict[str, Any]]) -> pd.DataFrame:
        rows = []
        for item in cmes:
            rows.append(
                {
                    "start_time": _to_datetime(item.get("time21_5")),
                    "impact_time": _to_datetime(item.get("estimatedShockArrivalTime")),
                    "speed": _safe_float(item.get("speed")) or 0.0,
                    "half_angle": _safe_float(item.get("halfAngle")) or 0.0,
                    "latitude": _safe_float(item.get("latitude")) or 0.0,
                    "longitude": _safe_float(item.get("longitude")) or 0.0,
                }
            )
        return pd.DataFrame(rows)

    def _build_flare_frame(self, flares: list[dict[str, Any]]) -> pd.DataFrame:
        rows = []
        for flare in flares:
            rows.append(
                {
                    "begin_time": _to_datetime(flare.get("beginTime")),
                    "class_type": flare.get("classType") or "",
                }
            )
        return pd.DataFrame(rows)

    def _aggregate_cme_features(self, cme_frame: pd.DataFrame, current_day: date) -> dict[str, float]:
        if cme_frame.empty:
            return {
                "cme_count_24h": 0.0,
                "earth_directed_cme_count_72h": 0.0,
                "max_cme_speed_72h": 0.0,
                "mean_cme_speed_72h": 0.0,
                "mean_cme_half_angle_72h": 0.0,
                "impact_count_24h": 0.0,
            }

        day_start = datetime.combine(current_day, datetime.min.time(), tzinfo=UTC)
        prev_24h = day_start - timedelta(days=1)
        prev_72h = day_start - timedelta(days=3)
        next_24h = day_start + timedelta(days=1)

        recent = cme_frame[cme_frame["start_time"].between(prev_72h, day_start, inclusive="left")]
        last_day = cme_frame[cme_frame["start_time"].between(prev_24h, day_start, inclusive="left")]
        impacts = cme_frame[cme_frame["impact_time"].between(day_start, next_24h, inclusive="left")]

        earth_directed = recent[
            (recent["longitude"].abs() <= 45.0) & (recent["latitude"].abs() <= 30.0)
        ]

        return {
            "cme_count_24h": float(len(last_day)),
            "earth_directed_cme_count_72h": float(len(earth_directed)),
            "max_cme_speed_72h": float(recent["speed"].max()) if not recent.empty else 0.0,
            "mean_cme_speed_72h": float(recent["speed"].mean()) if not recent.empty else 0.0,
            "mean_cme_half_angle_72h": float(recent["half_angle"].mean()) if not recent.empty else 0.0,
            "impact_count_24h": float(len(impacts)),
        }

    def _aggregate_flare_features(self, flare_frame: pd.DataFrame, current_day: date) -> dict[str, float]:
        if flare_frame.empty:
            return {
                "flare_count_24h": 0.0,
                "m_flare_count_72h": 0.0,
                "x_flare_count_72h": 0.0,
            }

        day_start = datetime.combine(current_day, datetime.min.time(), tzinfo=UTC)
        prev_24h = day_start - timedelta(days=1)
        prev_72h = day_start - timedelta(days=3)
        last_day = flare_frame[flare_frame["begin_time"].between(prev_24h, day_start, inclusive="left")]
        recent = flare_frame[flare_frame["begin_time"].between(prev_72h, day_start, inclusive="left")]

        return {
            "flare_count_24h": float(len(last_day)),
            "m_flare_count_72h": float(recent["class_type"].str.startswith("M").sum()),
            "x_flare_count_72h": float(recent["class_type"].str.startswith("X").sum()),
        }

    def _mean_prior_kp(self, daily_kp: dict[str, float], current_day: date, window_days: int) -> float:
        values = [
            daily_kp.get((current_day - timedelta(days=offset)).isoformat(), 0.0)
            for offset in range(1, window_days + 1)
        ]
        return float(sum(values) / len(values)) if values else 0.0


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
