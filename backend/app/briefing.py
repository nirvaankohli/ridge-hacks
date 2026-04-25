from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class CivilianBriefResponse(BaseModel):
    headline: str
    summary: str
    takeaways: list[str] = Field(default_factory=list)
    best_time: str
    what_to_do: str
    product_ideas: list[str] = Field(default_factory=list)
    source: str


@dataclass(slots=True)
class BriefingContext:
    analysis_date: str
    latitude: float
    model_prediction: str
    model_confidence: float
    status: dict[str, Any]
    visibility: dict[str, Any]
    aurora: dict[str, Any]
    infrastructure: dict[str, Any]


class CivilianBriefingService:
    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY")
        self._model = os.getenv("OPENAI_BRIEF_MODEL", "gpt-4o-mini")

    async def build(self, context: BriefingContext) -> CivilianBriefResponse:
        fallback = self._build_fallback(context)
        if not self._api_key:
            return fallback

        try:
            from openai import OpenAI
        except Exception:
            return fallback

        try:
            client = OpenAI()
            response = client.responses.parse(
                model=self._model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You write concise, calm, civilian-friendly space weather briefings. "
                            "Avoid jargon. Keep it practical and polished. "
                            "Also brainstorm a few product ideas that could improve the experience."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "analysis_date": context.analysis_date,
                                "latitude": context.latitude,
                                "model_prediction": context.model_prediction,
                                "model_confidence": context.model_confidence,
                                "status": context.status,
                                "visibility": context.visibility,
                                "aurora": context.aurora,
                                "infrastructure": context.infrastructure,
                            }
                        ),
                    },
                ],
                text_format=CivilianBriefResponse,
            )
            brief = response.output_parsed
            if brief:
                brief.source = "openai"
                return brief
        except Exception:
            return fallback

        return fallback

    def _build_fallback(self, context: BriefingContext) -> CivilianBriefResponse:
        prediction = (context.model_prediction or "quiet").lower()
        headline = {
            "quiet": "Quiet skies, low risk.",
            "watch": "Worth watching tonight.",
            "moderate": "Some aurora potential is building.",
            "high": "Strong storm conditions are possible.",
            "severe": "Major storm conditions are likely.",
        }.get(prediction, "Space weather update.")

        takeaways = [
            _takeaway_from_visibility(context.visibility),
            _takeaway_from_status(context.status),
            _takeaway_from_infrastructure(context.infrastructure),
        ]

        return CivilianBriefResponse(
            headline=headline,
            summary=(
                f"The model points to {prediction} conditions for {context.analysis_date}. "
                "This view is tuned for civilians: short, practical, and focused on what to expect."
            ),
            takeaways=[item for item in takeaways if item],
            best_time="Late evening to early morning if skies stay clear.",
            what_to_do=(
                "Check the north sky from a dark spot if the probability climbs and cloud cover stays low."
            ),
            product_ideas=[
                "Add a day-by-day forecast timeline.",
                "Let users compare two dates side by side.",
                "Turn the summary into an alert when the risk changes materially.",
            ],
            source="fallback",
        )


def _takeaway_from_visibility(visibility: dict[str, Any]) -> str:
    probability = visibility.get("adjusted_probability") or visibility.get("probability") or 0
    cloud_cover = visibility.get("cloud_cover_percent")
    if probability >= 70:
        return "Aurora odds are strong enough to make a trip worthwhile."
    if probability >= 35:
        return "There is a chance if the sky stays clear."
    if cloud_cover is not None:
        return f"Cloud cover is around {cloud_cover}%, which may limit visibility."
    return "Visibility is currently limited or uncertain."


def _takeaway_from_status(status: dict[str, Any]) -> str:
    kp = status.get("kp")
    bz = status.get("bz")
    if kp is None:
        return "Current solar-wind data is incomplete."
    if kp >= 6 or (bz is not None and bz < -10):
        return f"Solar conditions are active with Kp near {kp:.1f}."
    return f"Solar conditions are calm with Kp near {kp:.1f}."


def _takeaway_from_infrastructure(infrastructure: dict[str, Any]) -> str:
    level = (infrastructure.get("recommended_warning_level") or "QUIET").lower()
    if level in {"high", "severe"}:
        return "Some infrastructure regions deserve closer monitoring."
    return "Infrastructure risk is currently low."
