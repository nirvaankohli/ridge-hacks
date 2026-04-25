from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler


space_weather_scheduler = AsyncIOScheduler(timezone="UTC")


def configure_scheduler(space_weather_api) -> None:
    if space_weather_scheduler.get_jobs():
        return
    space_weather_scheduler.add_job(
        space_weather_api.poll_realtime_space_weather,
        "interval",
        minutes=1,
        id="poll_realtime_space_weather",
        replace_existing=True,
    )
    space_weather_scheduler.add_job(
        space_weather_api.poll_aurora_feed,
        "interval",
        minutes=5,
        id="poll_aurora_feed",
        replace_existing=True,
    )
    space_weather_scheduler.add_job(
        space_weather_api.poll_donki_data,
        "interval",
        minutes=15,
        id="poll_donki_data",
        replace_existing=True,
    )


async def warm_scheduler(space_weather_api) -> None:
    await space_weather_api.warm_cache()


def start_scheduler(space_weather_api) -> None:
    configure_scheduler(space_weather_api)
    if not space_weather_scheduler.running:
        space_weather_scheduler.start()


def stop_scheduler() -> None:
    if space_weather_scheduler.running:
        space_weather_scheduler.shutdown(wait=False)


def is_scheduler_running() -> bool:
    return bool(space_weather_scheduler.running)
