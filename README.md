# super-aff

> Auto bikin konten Shopee Affiliate: foto produk → slideshow + voice-over AI + caption + hashtag.

Bring Your Own Key (BYOK) studio yang ngubah link produk Shopee jadi paket konten siap upload — video slideshow MP4, voice-over AI, caption Bahasa Indonesia, dan daftar hashtag — dengan satu klik. Tidak ada auto-upload ke Shopee (sengaja: tetap di sisi yang aman secara TOS).

- **Mode Single**: paste link produk Shopee atau isi manual (judul + upload foto) → output konten lengkap.
- **Mode Bulk**: upload CSV banyak produk → batch render → ZIP berisi semua MP4 + caption + hashtag.
- **BYOK**: API key untuk LLM (caption/hashtag) & TTS (voice-over) disimpan **hanya di browser** (`localStorage`). Server tidak menyimpan apa-apa.
- **Provider-agnostic**: OpenAI, Anthropic, Google Gemini, Groq, OpenRouter, ElevenLabs, atau endpoint OpenAI-compatible apa saja.

## Tech stack

- `frontend/` — Next.js 16 (App Router) + Tailwind v4
- `backend/` — FastAPI + httpx + ffmpeg
- `ffmpeg` (lewat `imageio-ffmpeg`) di-bundle untuk komposisi MP4

## Quick start (Docker)

```bash
docker compose up -d --build
```

Buka <http://localhost:8081>, ke **Settings**, tempel API key, klik **Check API**, lalu ke **Single** atau **Bulk**.

## Local dev tanpa Docker

```bash
# backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# frontend (shell terpisah)
cd frontend
pnpm install
pnpm dev
```

Buka <http://localhost:3000>.

## Format CSV (Bulk Mode)

Header minimum (tidak case-sensitive):

```csv
url,judul,deskripsi
https://shopee.co.id/product/123456/789012,,
,Celana Jeans Pria Skinny,Bahan melar nyaman dipakai
```

- Kalau `url` diisi, kolom lain auto-scrape dari Shopee.
- Kalau `url` kosong, pakai `judul` + `deskripsi` manual (bisa juga upload foto manual nanti per row).

Output ZIP berisi `produk_001.mp4`, `produk_001.caption.txt`, `produk_001.hashtag.txt`, dst.

## Catatan Etika & Legal

Tool ini **tidak men-download ulang video produk dari seller asli** — itu pelanggaran hak cipta. Yang dipakai cuma **foto produk dari listing Shopee** (yang umumnya boleh dipakai affiliate marketer untuk promo) ditambah konten 100% baru: voice-over AI, caption AI, slideshow ffmpeg.

Tidak ada auto-upload ke Shopee. Anda upload manual via aplikasi Shopee, tetap mengikuti policy mereka.

## Struktur folder

```
super-aff/
├── backend/             FastAPI server (port 8000)
│   └── app/
│       ├── main.py
│       ├── routers/     /api/shopee, /api/content, /api/voiceover, /api/compose, /api/batch
│       ├── providers/   LLM + TTS adapters (BYOK)
│       ├── shopee/      Shopee URL scraper
│       └── compose/     ffmpeg slideshow pipeline
├── frontend/            Next.js 16 (port 3000)
│   └── src/
│       ├── app/         /, /single, /bulk, /settings
│       ├── components/
│       └── lib/
└── docker-compose.yml
```
