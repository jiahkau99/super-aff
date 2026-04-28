from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.providers.tts import TTSError, tts
from app.schemas import GenerateVoiceoverRequest

router = APIRouter(prefix="/api/voiceover", tags=["voiceover"])


@router.post("/generate")
async def generate_voiceover(req: GenerateVoiceoverRequest) -> Response:
    if not req.text.strip():
        raise HTTPException(400, "Teks kosong.")
    try:
        audio = await tts(req.creds, req.text)
    except TTSError as exc:
        raise HTTPException(502, str(exc)) from exc
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'inline; filename="voiceover.mp3"'},
    )
