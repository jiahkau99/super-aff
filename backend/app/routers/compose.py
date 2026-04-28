from __future__ import annotations

import base64
import binascii
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

from app.compose import compose_slideshow
from app.schemas import ComposeSlideshowRequest

router = APIRouter(prefix="/api/compose", tags=["compose"])


def _decode_b64(data: str, label: str) -> bytes:
    s = data.strip()
    # Strip data URL prefix if present.
    if s.startswith("data:"):
        comma = s.find(",")
        if comma >= 0:
            s = s[comma + 1 :]
    try:
        return base64.b64decode(s, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, f"base64 invalid pada {label}: {exc}") from exc


@router.post("/slideshow")
async def compose_slideshow_endpoint(req: ComposeSlideshowRequest) -> Response:
    if not req.images_b64:
        raise HTTPException(400, "Butuh minimal 1 gambar.")

    work = Path(tempfile.mkdtemp(prefix="super-aff-job-"))
    try:
        # Save images
        image_paths: list[Path] = []
        for i, b64 in enumerate(req.images_b64):
            data = _decode_b64(b64, f"images_b64[{i}]")
            p = work / f"src_{i:03d}.bin"
            p.write_bytes(data)
            image_paths.append(p)

        # Save audio if any
        audio_path: Path | None = None
        if req.audio_b64:
            audio_bytes = _decode_b64(req.audio_b64, "audio_b64")
            audio_path = work / "audio.mp3"
            audio_path.write_bytes(audio_bytes)

        out = work / "out.mp4"
        try:
            compose_slideshow(
                image_paths=image_paths,
                audio_path=audio_path,
                out_path=out,
                target_resolution=req.target_resolution,
                duration_per_image=req.duration_per_image,
                watermark_text=req.watermark_text,
                subtitle_text=req.subtitle_text,
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(500, str(exc)) from exc

        body = out.read_bytes()
        return Response(
            content=body,
            media_type="video/mp4",
            headers={
                "Content-Disposition": 'attachment; filename="super-aff-slideshow.mp4"'
            },
        )
    finally:
        # The Response body is already in memory, so we can clean up the temp dir.
        import shutil

        shutil.rmtree(work, ignore_errors=True)
