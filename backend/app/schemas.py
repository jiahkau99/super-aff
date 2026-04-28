from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LLMProvider = Literal[
    "openai",
    "anthropic",
    "gemini",
    "groq",
    "openrouter",
    "deepseek",
    "openai_compatible",
]

TTSProvider = Literal[
    "elevenlabs",
    "openai",
    "gemini",
    "minimax",
    "openai_compatible",
]


class LLMCreds(BaseModel):
    """Bring-your-own-key payload for LLM calls."""

    provider: LLMProvider
    api_key: str
    model: str | None = None
    base_url: str | None = None


class TTSCreds(BaseModel):
    """Bring-your-own-key payload for TTS calls."""

    provider: TTSProvider
    api_key: str
    model: str | None = None
    voice: str | None = None
    base_url: str | None = None


class ShopeeProduct(BaseModel):
    """Normalised Shopee product info."""

    title: str
    description: str = ""
    price: int | None = None  # Rupiah
    currency: str = "IDR"
    images: list[str] = Field(default_factory=list)
    rating_star: float | None = None
    historical_sold: int | None = None
    shop_name: str | None = None
    item_id: int | None = None
    shop_id: int | None = None
    source_url: str | None = None


class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    ok: bool
    product: ShopeeProduct | None = None
    error: str | None = None


class GenerateContentRequest(BaseModel):
    """Generate caption + hashtags from product title/description."""

    title: str
    description: str = ""
    price: int | None = None
    extra_context: str = ""
    language: str = "id"  # 'id' | 'en'
    tone: str = "santai-promosi"  # mis. "formal", "fun", "hardsell"
    hashtag_count: int = 25
    creds: LLMCreds


class GenerateContentResponse(BaseModel):
    caption: str
    hashtags: list[str]
    voiceover_script: str


class GenerateVoiceoverRequest(BaseModel):
    text: str
    creds: TTSCreds


# Returns audio/mpeg (mp3) bytes directly via FastAPI Response,
# so no JSON response model.


class ComposeSlideshowRequest(BaseModel):
    """In-memory compose: images + audio + caption -> mp4."""

    title: str
    images_b64: list[str]  # base64-encoded JPEG/PNG bytes
    audio_b64: str | None = None  # base64 mp3, optional
    caption: str = ""
    watermark_text: str = ""
    duration_per_image: float = 3.0  # seconds (used if no audio)
    target_resolution: tuple[int, int] = (720, 1280)


class ComposeSlideshowResponse(BaseModel):
    ok: bool
    error: str | None = None
    # Returns mp4 bytes via Response, so this schema is mostly for errors


class BatchCSVRow(BaseModel):
    url: str = ""
    judul: str = ""
    deskripsi: str = ""


class BatchPlanRequest(BaseModel):
    rows: list[BatchCSVRow]


class BatchPlanResponse(BaseModel):
    """Returns the list of products that would be processed (after scraping)."""

    items: list[dict]
