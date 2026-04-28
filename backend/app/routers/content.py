from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException

from app.providers.llm import LLMError, chat_completion
from app.schemas import GenerateContentRequest, GenerateContentResponse

router = APIRouter(prefix="/api/content", tags=["content"])


SYSTEM_PROMPT = """\
Kamu adalah copywriter Shopee Affiliate yang jago bikin konten viral di Indonesia.
Tugas: dari info produk yang dikasih, hasilkan tiga output dalam JSON:
1. "caption": caption posting Shopee Video yang singkat (maks 150 kata),
   gaya {tone}, bahasa {language}, ada hook di kalimat pertama, ada call-to-action di akhir
   ("klik link di profil/keranjang oren"). Jangan pakai emoji berlebihan (maks 4 emoji).
2. "hashtags": daftar {hashtag_count} hashtag relevan dalam {language}, tanpa tanda #,
   campuran (a) hashtag spesifik produk, (b) brand/kategori, (c) general affiliate Shopee.
   Semua huruf kecil, tanpa spasi, tanpa duplikat.
3. "voiceover_script": script untuk voice-over video 25-35 detik, bahasa {language},
   gaya bicara natural ngomong ke kamera, 3-5 kalimat pendek. JANGAN pakai markdown,
   asterisk, atau placeholder. Output siap dibaca.

Output WAJIB JSON valid satu objek dengan kunci persis: caption, hashtags, voiceover_script.
Jangan ada teks pembuka/penutup di luar JSON."""


def _build_user_prompt(req: GenerateContentRequest) -> str:
    parts = [f"Judul produk: {req.title.strip()}"]
    if req.description.strip():
        parts.append(f"Deskripsi: {req.description.strip()[:1500]}")
    if req.price:
        parts.append(f"Harga: Rp{req.price:,}".replace(",", "."))
    if req.extra_context.strip():
        parts.append(f"Konteks tambahan: {req.extra_context.strip()}")
    return "\n".join(parts)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(raw: str) -> dict:
    """Tolerate models that wrap JSON in code fences or add trailing prose."""
    s = raw.strip()
    m = _JSON_FENCE_RE.search(s)
    if m:
        s = m.group(1)
    # Find first '{' and last '}' as a fallback
    if not s.startswith("{"):
        i = s.find("{")
        j = s.rfind("}")
        if i >= 0 and j > i:
            s = s[i : j + 1]
    return json.loads(s)


@router.post("/generate", response_model=GenerateContentResponse)
async def generate_content(req: GenerateContentRequest) -> GenerateContentResponse:
    if not req.title.strip():
        raise HTTPException(400, "Field 'title' wajib diisi.")

    system = SYSTEM_PROMPT.format(
        tone=req.tone,
        language="Bahasa Indonesia" if req.language == "id" else "English",
        hashtag_count=req.hashtag_count,
    )
    user = _build_user_prompt(req)

    try:
        raw = await chat_completion(req.creds, system=system, user=user)
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc

    try:
        obj = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            502,
            f"LLM tidak mengembalikan JSON valid. Output mentah: {raw[:600]!r}",
        ) from exc

    caption = (obj.get("caption") or "").strip()
    hashtags_raw = obj.get("hashtags") or []
    if isinstance(hashtags_raw, str):
        hashtags_raw = [h.strip() for h in re.split(r"[,\s]+", hashtags_raw) if h.strip()]
    hashtags = [
        re.sub(r"^#+", "", str(h)).strip().lower().replace(" ", "")
        for h in hashtags_raw
        if str(h).strip()
    ]
    # de-dupe preserving order
    seen: set[str] = set()
    hashtags = [h for h in hashtags if not (h in seen or seen.add(h))]
    voiceover_script = (obj.get("voiceover_script") or "").strip()

    if not caption or not voiceover_script:
        raise HTTPException(
            502,
            f"LLM mengembalikan field kosong. Caption={caption!r}, voice={voiceover_script!r}",
        )

    return GenerateContentResponse(
        caption=caption,
        hashtags=hashtags,
        voiceover_script=voiceover_script,
    )
