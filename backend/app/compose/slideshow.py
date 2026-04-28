"""Compose a portrait slideshow MP4 from product images + voice-over audio.

Pipeline:
  1. Normalize each input image to target resolution (default 720x1280) with
     letterbox padding so we don't crop the product weirdly.
  2. Build an ffmpeg `concat` filter: each image gets `duration_per_image`
     seconds (or proportionally divided by audio length if audio provided).
  3. Apply a Ken-Burns-style slow zoom-in on each image via `zoompan` for
     a more dynamic feel.
  4. Mix the voice-over audio (mp3) into the output MP4.
  5. Optionally burn a watermark text overlay.

Returns the path to the generated MP4. The caller owns cleanup.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps


def _ffmpeg_bin() -> str:
    """Use the bundled ffmpeg binary so we don't depend on apt install."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try common Linux fonts; fall back to default if none found."""
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_watermark(im: Image.Image, text: str) -> None:
    """Burn a centered-bottom watermark with black outline onto the image."""
    if not text.strip():
        return
    draw = ImageDraw.Draw(im)
    w, h = im.size
    font_size = max(28, int(w * 0.055))
    font = _load_font(font_size)

    # Word-wrap to keep within 90% of width.
    max_w = int(w * 0.9)
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        candidate = (cur + " " + word).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_w or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)

    line_h = int(font_size * 1.2)
    total_h = line_h * len(lines)
    y = h - total_h - int(h * 0.07)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (w - line_w) // 2
        # Black outline
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)]:
            draw.text((x + dx, y + dy), line, fill=(0, 0, 0), font=font)
        draw.text((x, y), line, fill=(255, 255, 255), font=font)
        y += line_h


def _normalize_image(
    src: Path, dest: Path, size: tuple[int, int], *, watermark_text: str = ""
) -> None:
    """Letterbox-resize an image to exactly `size` (width, height) and optionally watermark."""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        canvas = ImageOps.pad(im, size, color=(0, 0, 0))
        if watermark_text:
            _draw_watermark(canvas, watermark_text)
        canvas.save(dest, "JPEG", quality=92)


def _audio_duration_sec(audio_path: Path) -> float | None:
    """Probe audio duration via ffmpeg (parses stderr)."""
    try:
        proc = subprocess.run(
            [_ffmpeg_bin(), "-i", str(audio_path), "-hide_banner"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    err = proc.stderr or ""
    # e.g. "Duration: 00:00:32.45, start: ..."
    for line in err.splitlines():
        s = line.strip()
        if s.startswith("Duration:"):
            try:
                hms = s.split(",")[0].split("Duration:", 1)[1].strip()
                h, m, sec = hms.split(":")
                return int(h) * 3600 + int(m) * 60 + float(sec)
            except (ValueError, IndexError):
                return None
    return None


def compose_slideshow(
    *,
    image_paths: Sequence[Path],
    audio_path: Path | None = None,
    out_path: Path,
    target_resolution: tuple[int, int] = (720, 1280),
    duration_per_image: float = 3.0,
    watermark_text: str = "",
    fps: int = 30,
) -> Path:
    """Compose slideshow MP4. Returns out_path."""
    if not image_paths:
        raise ValueError("Butuh minimal 1 image.")

    work = Path(tempfile.mkdtemp(prefix="super-aff-compose-"))
    try:
        # 1. Normalize images (and burn watermark via PIL for portability)
        norm_paths: list[Path] = []
        for i, src in enumerate(image_paths):
            dest = work / f"img_{i:03d}.jpg"
            _normalize_image(src, dest, target_resolution, watermark_text=watermark_text)
            norm_paths.append(dest)

        # 2. Decide per-image duration based on audio length if provided.
        if audio_path is not None and audio_path.exists():
            audio_dur = _audio_duration_sec(audio_path) or (duration_per_image * len(norm_paths))
            per_img = max(1.5, audio_dur / max(1, len(norm_paths)))
        else:
            per_img = duration_per_image
            audio_dur = per_img * len(norm_paths)

        # 3. Build concat input file
        concat_txt = work / "concat.txt"
        lines: list[str] = []
        for p in norm_paths:
            lines.append(f"file '{p.as_posix()}'")
            lines.append(f"duration {per_img:.3f}")
        # ffmpeg concat demuxer needs the last image listed once more without duration
        lines.append(f"file '{norm_paths[-1].as_posix()}'")
        concat_txt.write_text("\n".join(lines), encoding="utf-8")

        # 4. Build filter chain: zoompan Ken-Burns. Watermark already baked into images.
        w, h = target_resolution
        zoom_frames = max(1, int(per_img * fps))
        vfilter = (
            f"scale={w*2}:{h*2},"
            f"zoompan=z='min(zoom+0.0015,1.20)':d={zoom_frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={w}x{h}:fps={fps},"
            f"format=yuv420p"
        )

        # 5. Run ffmpeg
        cmd: list[str] = [
            _ffmpeg_bin(),
            "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        ]
        if audio_path is not None and audio_path.exists():
            cmd += ["-i", str(audio_path)]
        cmd += [
            "-vf", vfilter,
            "-r", str(fps),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            "-crf", "22",
            "-movflags", "+faststart",
        ]
        if audio_path is not None and audio_path.exists():
            cmd += [
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-map", "0:v:0",
                "-map", "1:a:0",
            ]
        else:
            cmd += ["-an", "-t", f"{audio_dur:.3f}"]
        cmd += [str(out_path)]

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg gagal (rc={proc.returncode}). stderr tail:\n{proc.stderr[-1500:]}"
            )
        return out_path
    finally:
        shutil.rmtree(work, ignore_errors=True)
