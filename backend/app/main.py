from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import batch, compose, content, shopee, util, voiceover

app = FastAPI(
    title="super-aff",
    description=(
        "Auto bikin konten Shopee Affiliate: foto produk -> "
        "slideshow + voice-over AI + caption + hashtag."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shopee.router)
app.include_router(content.router)
app.include_router(voiceover.router)
app.include_router(compose.router)
app.include_router(batch.router)
app.include_router(util.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
