from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any


class SpaceWeatherCache:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._snapshot: dict[str, Any] = {
            "realtime": {},
            "aurora": {},
            "donki": {},
            "source_timestamps": {},
            "source_errors": {},
            "last_updated": None,
        }

    async def get_snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return deepcopy(self._snapshot)

    async def update_realtime(self, payload: dict[str, Any]) -> None:
        await self._update_section("realtime", payload, "realtime")

    async def update_aurora(self, payload: dict[str, Any]) -> None:
        await self._update_section("aurora", payload, "aurora")

    async def update_donki(self, payload: dict[str, Any]) -> None:
        await self._update_section("donki", payload, "donki")

    async def mark_error(self, source: str, error: str) -> None:
        async with self._lock:
            self._snapshot["source_errors"][source] = error

    async def clear_error(self, source: str) -> None:
        async with self._lock:
            self._snapshot["source_errors"].pop(source, None)

    async def mark_success(self, source: str) -> None:
        async with self._lock:
            self._snapshot["source_timestamps"][source] = _now_iso()
            self._snapshot["source_errors"].pop(source, None)

    async def _update_section(self, section: str, payload: dict[str, Any], source: str) -> None:
        async with self._lock:
            timestamp = _now_iso()
            self._snapshot[section] = payload
            self._snapshot["source_timestamps"][source] = timestamp
            self._snapshot["last_updated"] = timestamp
            self._snapshot["source_errors"].pop(source, None)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


space_weather_cache = SpaceWeatherCache()
