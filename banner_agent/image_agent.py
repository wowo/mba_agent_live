"""Nano Banana sub-agent — banner image generation only."""

import uuid
from pathlib import Path
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types
import os
from typing import Optional
from pydantic import BaseModel, Field
from google.adk.agents import Agent


NANO_BANANA_MODEL = os.environ.get(
    "NANO_BANANA_MODEL", "gemini-3.1-flash-image-preview"
)

GENERATED_DIR = Path(__file__).resolve().parent / "generated"

async def save_banner_image_artifact(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> None:
    """Save inline image parts as session artifacts (ADK Web)."""
    if not llm_response.content or not llm_response.content.parts:
        return None

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    for part in llm_response.content.parts:
        inline = part.inline_data
        if not inline or not inline.mime_type or not inline.mime_type.startswith("image/"):
            continue
        ext = "png" if "png" in inline.mime_type else "jpg"
        artifact_name = f"banner_{uuid.uuid4().hex}.{ext}"
        (GENERATED_DIR / artifact_name).write_bytes(inline.data)
        await callback_context.save_artifact(filename=artifact_name, artifact=part)
    return None


class BannerBrief(BaseModel):
    """Creative brief passed from the orchestrator."""

    home_team: str
    away_team: str
    kickoff_display: str = Field(description="e.g. Sat 20:45")
    odds_home: float
    odds_away: float
    bonus_code: str
    bonus_amount: str
    weather_phrase: str
    skyline_landmark: str
    odds_draw: Optional[float] = Field(
        default=None,
        description="Omit when the sport has no draw",
    )


banner_image_agent = Agent(
    name="banner_image_agent",
    description="Generates one 16:9 iGaming promotional banner from a structured brief.",
    model=NANO_BANANA_MODEL,
    input_schema=BannerBrief,
    generate_content_config=genai_types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    ),
    after_model_callback=save_banner_image_artifact,
    instruction="""
Produce ONE finished 16:9 web banner: dark navy/gold iGaming style.
Show home vs away, kickoff, odds chips, bonus code/amount, weather and skyline.
Image output only — no HTML or code.
""",
)