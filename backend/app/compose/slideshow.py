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

import re
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


def _split_subtitle_segments(text: str) -> list[str]:
    """Split a free-form script into short subtitle segments.

    The voice-over text we get back from the LLM is one long paragraph;
    burning it as a single block of text on screen looks awful and overlaps
    products visually. We split on sentence terminators and newlines, then
    further break long runs at commas / semicolons so each segment fits
    comfortably on two lines of the on-screen overlay.
    """

    if not text or not text.strip():
        return []
    # Initial split on sentence boundaries + line breaks.
    raw = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    # Further break overlong sentences (>80 chars) at commas/semicolons.
    out: list[str] = []
    for chunk in raw:
        chunk = chunk.strip()
        if not chunk:
            continue
        if len(chunk) <= 80:
            out.append(chunk)
            continue
        for sub in re.split(r"(?<=[,;])\s+", chunk):
            sub = sub.strip()
            if sub:
                out.append(sub)
    return out


def _format_srt_timestamp(seconds: float) -> str:
    """`HH:MM:SS,mmm` (SRT comma-separated milliseconds, not period)."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:  # rounding edge
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt(
    segments: Sequence[str], total_duration: float
) -> str:
    """Distribute segments across ``total_duration`` weighted by char count.

    Char-weighting roughly matches speaking pace, so a one-word “Ya.” takes
    much less screen time than a 60-character sentence. We don’t do real
    forced alignment (Whisper) — that would be heavy and require an extra
    model. Even distribution would be a regression for variable-length
    sentences, so weighting is the cheap-but-decent middle ground.
    """

    if not segments or total_duration <= 0:
        return ""
    weights = [max(1, len(seg)) for seg in segments]
    total_w = sum(weights)
    out_lines: list[str] = []
    cursor = 0.0
    for i, seg in enumerate(segments):
        share = total_duration * weights[i] / total_w
        # Bound each segment between 1.0s (readable minimum) and 6.0s
        # (TikTok-style fast pacing). The bounds may push us past
        # total_duration on extreme inputs — ffmpeg simply truncates trailing
        # subtitles past EOF, so this is safe.
        share = min(6.0, max(1.0, share))
        start = cursor
        end = cursor + share
        cursor = end
        out_lines.append(str(i + 1))
        out_lines.append(
            f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}"
        )
        out_lines.append(seg)
        out_lines.append("")
    return "\n".join(out_lines)


def compose_slideshow(
    *,
    image_paths: Sequence[Path],
    audio_path: Path | None = None,
    out_path: Path,
    target_resolution: tuple[int, int] = (720, 1280),
    duration_per_image: float = 3.0,
    watermark_text: str = "",
    subtitle_text: str = "",
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

        # 4b. Optional subtitle burn-in. We pass ffmpeg the SRT path as a
        # *relative* filename and run with cwd=work, because the `subtitles`
        # filter syntax interprets `:` as an option separator. Absolute
        # Windows paths like `C:\foo` would be parsed as filter options. The
        # font name needs to exist on the runtime machine; on the Tauri
        # Windows bundle this resolves via libass’s default font
        # configuration (it’ll fall back to Arial if DejaVu Sans Bold is not
        # installed, which is fine).
        if subtitle_text and subtitle_text.strip():
            segments = _split_subtitle_segments(subtitle_text)
            if segments:
                srt = _build_srt(segments, audio_dur)
                srt_path = work / "subs.srt"
                srt_path.write_text(srt, encoding="utf-8")
                style = (
                    "FontName=DejaVu Sans Bold,FontSize=22,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "BorderStyle=1,Outline=2,Shadow=0,"
                    "Alignment=2,MarginV=80"
                )
                # Escape commas in style block so they’re not treated as
                # filter-graph separators.
                vfilter += f",subtitles=subs.srt:force_style='{style}'"

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

        # cwd=work so the `subtitles=subs.srt` filter resolves relative to
        # the temp dir without leaking absolute paths into the filter graph.
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=str(work)
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg gagal (rc={proc.returncode}). stderr tail:\n{proc.stderr[-1500:]}"
            )
        return out_path
    finally:
        shutil.rmtree(work, ignore_errors=True)
