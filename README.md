# super-aff

> **Auto bikin konten Shopee Affiliate**: foto produk → slideshow MP4 + voice-over AI + caption + hashtag, semua dalam 1 klik. **Tidak ada auto-upload** ke Shopee (sengaja, biar aman dari ToS).

Bring Your Own Key (BYOK) studio yang ngubah link produk Shopee jadi paket konten siap upload. Anda upload manual ke aplikasi Shopee — tetap mengikuti policy mereka.

- **Mode Single** — paste link Shopee atau isi manual (judul + upload foto) → MP4 + caption + hashtag.
- **Mode Bulk** — upload CSV banyak produk → batch render → ZIP berisi semua MP4 + caption + hashtag.
- **BYOK** — API key disimpan **hanya di browser** (`localStorage`). Server super-aff tidak nyimpen apa-apa, key cuma di-forward saat user klik tombol.
- **Provider-agnostic** — LLM (caption/hashtag/script): OpenAI, Anthropic, Google Gemini, Groq, OpenRouter, DeepSeek, MiniMax (via OpenAI-compatible), atau endpoint OpenAI-compatible apa saja. TTS (voice-over): ElevenLabs, OpenAI, Gemini, **MiniMax T2A** (Indonesian voice built-in), atau OpenAI-compatible.

---

## Daftar isi

- [Install Windows (.exe — paling gampang untuk user)](#install-windows-exe--paling-gampang-untuk-user)
- [Quick start (Docker — paling gampang)](#quick-start-docker--paling-gampang)
- [Run di PC tanpa Docker (Windows / macOS / Linux)](#run-di-pc-tanpa-docker-windows--macos--linux)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Clone repo](#2-clone-repo)
  - [3. Install backend (Python + ffmpeg)](#3-install-backend-python--ffmpeg)
  - [4. Install frontend (Node.js + pnpm)](#4-install-frontend-nodejs--pnpm)
  - [5. Konfigurasi alamat backend (PENTING untuk dev mode)](#5-konfigurasi-alamat-backend-penting-untuk-dev-mode)
  - [6. Jalankan keduanya](#6-jalankan-keduanya)
  - [7. Setup BYOK API keys di browser](#7-setup-byok-api-keys-di-browser)
- [Pakai MiniMax (LLM + TTS dengan 1 key)](#pakai-minimax-llm--tts-dengan-1-key)
- [Format CSV (Bulk Mode)](#format-csv-bulk-mode)
- [Troubleshooting](#troubleshooting)
- [Tech stack](#tech-stack)
- [Struktur folder](#struktur-folder)
- [Catatan etika & legal](#catatan-etika--legal)

---

## Install Windows (.exe — paling gampang untuk user)

Aplikasi desktop Windows (Tauri) yang tinggal di-double-click. Tidak perlu install Python, Node, atau Docker — semua sudah di-bundle.

1. Buka halaman **[Releases](https://github.com/andelaiceee-code/super-aff/releases)** di repo ini.
2. Download installer terbaru: **`super-aff_<versi>_x64-setup.exe`**.
3. Jalankan installer → klik **Install** → buka **super-aff** dari Start Menu.
4. Aplikasi terbuka dalam window sendiri (bukan browser). Backend FastAPI jalan otomatis di `127.0.0.1:8765` di belakang layar.
5. Pertama kali, buka tab **Settings** → tempel API key LLM (wajib) + TTS (opsional). Key disimpan **lokal di komputer Anda**, tidak pernah dikirim ke server kami.

**Kenapa pakai .exe lokal?** Saat aplikasi jalan di PC Anda, request scrape Shopee keluar dari **IP rumah/kantor Anda** (bukan IP server cloud). Shopee jauh lebih jarang block IP residential dibanding IP datacenter — jadi success rate scrape-nya naik signifikan.

**Catatan:**
- Hanya Windows 10/11 64-bit. macOS / Linux build belum tersedia.
- Pertama kali run mungkin Windows SmartScreen warning (installer belum signed). Klik **More info → Run anyway**.
- Untuk uninstall: Settings → Apps → super-aff → Uninstall.

Kalau Anda ingin compile sendiri dari source, lihat bagian [Build .exe sendiri (untuk developer)](#build-exe-sendiri-untuk-developer) di bawah.

---

## Quick start (Docker — paling gampang)

Kalau punya Docker Desktop / Docker Engine, ini cara tercepat:

```bash
git clone https://github.com/andelaiceee-code/super-aff.git
cd super-aff
docker compose up -d --build
```

Tunggu ~2 menit (build pertama kali). Lalu buka <http://localhost:8081>.

```bash
# cek apakah sudah jalan
docker compose ps
docker compose logs -f web backend
```

Untuk berhenti / cleanup:

```bash
docker compose down          # stop containers
docker compose down -v       # stop + hapus volumes
```

> Docker mode pakai Caddy reverse proxy: frontend di port 8081, backend di port 8000 (internal), `/api/*` otomatis di-route ke backend. Anda **tidak perlu** ngeset `NEXT_PUBLIC_API_BASE` kalau pakai Docker.

---

## Run di PC tanpa Docker (Windows / macOS / Linux)

Kalau gak mau Docker, bisa run native. Lebih cepat untuk development & debugging.

### 1. Prerequisites

| Tools | Versi minimum | Cara install |
|---|---|---|
| **Git** | 2.30+ | <https://git-scm.com/downloads> |
| **Python** | 3.11+ | <https://www.python.org/downloads/> (Windows: centang "Add Python to PATH") |
| **uv** (Python package manager) | latest | <https://docs.astral.sh/uv/getting-started/installation/> |
| **Node.js** | 20.x atau 22.x LTS | <https://nodejs.org/> (atau pakai [Volta](https://volta.sh)) |
| **pnpm** | 9.x+ | `npm install -g pnpm` (atau pakai corepack: `corepack enable pnpm`) |
| **ffmpeg** | tidak perlu install manual | otomatis di-bundle via `imageio-ffmpeg` saat backend `uv sync` |

**Quick install — uv** (semua OS):

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Quick install — pnpm**:

```bash
# semua OS, butuh Node.js terinstall
npm install -g pnpm
```

### 2. Clone repo

```bash
git clone https://github.com/andelaiceee-code/super-aff.git
cd super-aff
```

### 3. Install backend (Python + ffmpeg)

```bash
cd backend
uv sync
```

`uv sync` baca `pyproject.toml` + `uv.lock` dan install semua dependency (FastAPI, httpx, imageio-ffmpeg, dst.) ke virtualenv lokal di `backend/.venv`.

Test backend bisa start:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Buka <http://127.0.0.1:8000/healthz> di browser → harus tampil `{"status":"ok"}`. Tekan `Ctrl+C` untuk stop sementara.

### 4. Install frontend (Node.js + pnpm)

Buka **terminal baru** (jangan tutup yang backend), masuk ke folder frontend:

```bash
cd super-aff/frontend
pnpm install
```

### 5. Konfigurasi alamat backend (PENTING untuk dev mode)

Saat pakai `pnpm dev` (Next.js dev server), Next.js **tidak ada reverse proxy** — kalau frontend manggil `/api/...` dia 404 karena tidak ada yg listen di port 3000 untuk `/api`. Solusi: kasih tau frontend di mana backend-nya via env var.

Buat file `frontend/.env.local`:

```bash
# super-aff/frontend/.env.local
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

Cara cepat (Linux/macOS):

```bash
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > frontend/.env.local
```

Windows PowerShell:

```powershell
"NEXT_PUBLIC_API_BASE=http://localhost:8000" | Out-File -Encoding ascii frontend/.env.local
```

> File ini **tidak di-commit** (di-ignore di `.gitignore`). Kalau pakai Docker, **lewati** langkah ini — Caddy yg ngurus.

### 6. Jalankan keduanya

Anda butuh **2 terminal** terbuka bersamaan:

**Terminal 1 — backend** (di folder `super-aff/backend`):

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Biarkan jalan. Kalau Anda edit kode backend, dia auto-reload.

**Terminal 2 — frontend** (di folder `super-aff/frontend`):

```bash
pnpm dev
```

Tunggu `✓ Ready in …`, lalu buka <http://localhost:3000>.

### 7. Setup BYOK API keys di browser

1. Buka <http://localhost:3000/settings>.
2. **LLM** — pilih provider, paste API key, optional model + base URL.
3. **TTS** (opsional, kalau gak pengen voice-over silent slideshow) — pilih provider, paste key, optional voice ID.
4. Klik **Save** — muncul "Tersimpan di browser." berarti aman.
5. Pindah ke **Single** atau **Bulk** dan mulai bikin konten.

---

## Pakai MiniMax (LLM + TTS dengan 1 key)

Kalau Anda punya 1 key MiniMax, Anda bisa pakai ke **dua-duanya** — caption/hashtag/script (LLM) **dan** voice-over MP3 (TTS) — tanpa key tambahan.

### LLM caption/hashtag (MiniMax via OpenAI-compatible)

Di `/settings`:

| Field | Isi |
|---|---|
| Provider | **OpenAI-compatible (custom)** |
| API Key | `sk-…` (key MiniMax Anda) |
| Model | `MiniMax-M2.1` (atau `MiniMax-M2`, `MiniMax-M2.5`, `MiniMax-M2.7` — tergantung plan key Anda) |
| Base URL | `https://api.minimax.io/v1` |

> ⚠️ Beberapa plan MiniMax cuma boleh akses model tertentu. Kalau dapat error `your current token plan not support model, …`, ganti ke model lain dari list di atas.

### TTS voice-over (MiniMax T2A)

Di `/settings`:

| Field | Isi |
|---|---|
| Provider | **MiniMax T2A (Indonesian)** |
| API Key | `sk-…` (key yang sama) |
| Model | kosongin = pakai default `speech-2.8-hd`. Bisa juga `speech-02-hd`, `speech-2.6-hd`, `speech-2.6-turbo`, `speech-2.8-turbo` (tergantung plan). |
| Voice ID | kosongin = pakai default `Indonesian_SweetGirl`. Voice Indonesia lainnya: `Indonesian_ReservedYoungMan`, `Indonesian_CharmingGirl`, `Indonesian_CalmWoman`. Lihat [System Voice ID list](https://platform.minimax.io/docs/faq/system-voice-id). |

Klik **Save**, lalu di `/single` klik **Generate konten** — MP4 sekarang punya voice-over Indonesia natural.

---

## Format CSV (Bulk Mode)

Header minimum (tidak case-sensitive):

```csv
url,judul,deskripsi
https://shopee.co.id/product/123456/789012,,
,Celana Jeans Pria Skinny,Bahan melar nyaman dipakai
https://s.shopee.co.id/3VgfWc4ajO,,
```

- Kalau `url` diisi, kolom lain auto-scrape dari Shopee (kalau Shopee API kena anti-bot, baris itu di-skip dengan warning).
- Kalau `url` kosong, pakai `judul` + `deskripsi` manual.
- Shortlink `s.shopee.co.id/...` juga didukung (auto follow redirect).

Output ZIP berisi `produk_001.mp4`, `produk_001.caption.txt`, `produk_001.hashtag.txt`, dst.

---

## Troubleshooting

### Frontend 404 saat klik Scrape / Generate (dev mode)

```
HTTP 404: This page could not be found.
```

Frontend dev server tidak ada reverse proxy ke backend. Pastikan `frontend/.env.local` sudah diisi `NEXT_PUBLIC_API_BASE=http://localhost:8000` lalu **restart `pnpm dev`** (env var hanya dibaca saat startup). Lihat [step 5](#5-konfigurasi-alamat-backend-penting-untuk-dev-mode).

Atau pakai Docker mode di mana Caddy ngurus proxy.

### "Gagal akses Shopee API: Shopee API menolak request (HTTP 403)"

Ini **expected** dari IP server / VPN. Shopee anti-bot block hampir semua server IP. Solusi: lanjut isi judul + upload foto manual di section 2 di halaman Single. Tool ini memang dirancang untuk fallback ke manual saat Shopee API ke-block.

### "your current token plan not support model, …"

API key MiniMax Anda tidak punya akses ke model tersebut. Coba model lain:
- LLM: `MiniMax-M2`, `MiniMax-M2.1`, `MiniMax-M2.5`, `MiniMax-M2.7` (variant `*-highspeed` biasanya butuh paid plan)
- TTS: `speech-2.8-hd`, `speech-02-hd`, `speech-2.6-hd` (variant `*-turbo` biasanya butuh paid plan)

### Port 3000 / 8000 / 8081 sudah dipakai

Stop apapun yg pakai port itu, atau ganti port:
- Backend: `uv run uvicorn app.main:app --reload --port 8001` lalu update `frontend/.env.local` ke `http://localhost:8001`.
- Frontend: `pnpm dev --port 3001`.
- Docker: ubah `PORT=8082` (atau apapun) di `.env` sebelum `docker compose up`.

### `uv sync` / `pnpm install` lemot di Indonesia

uv pakai default registry `https://pypi.org` — biasanya cukup cepat. pnpm bisa pakai mirror Indonesia:

```bash
pnpm config set registry https://registry.npmmirror.com
```

### "command not found: uv" / "command not found: pnpm"

Setelah install, restart terminal supaya `PATH` ke-reload. Di Windows mungkin perlu logout+login.

### ffmpeg not found

Jangan install ffmpeg manual. Backend pakai `imageio-ffmpeg` yg sudah include binary cross-platform — tinggal `uv sync`.

### Caption mengandung `<think>` token

Beberapa model reasoning (MiniMax-M2.x, DeepSeek-R1, dll.) emit reasoning trace `<think>...</think>` sebelum output JSON-nya. Backend `_extract_json` sudah handle ini dengan cari `{...}` pertama.

---

## Build .exe sendiri (untuk developer)

Yang dibutuhkan di mesin developer (Windows direkomendasikan, atau pakai GitHub Actions runner `windows-latest`):

- **Rust** stable + target `x86_64-pc-windows-msvc` (`rustup target add x86_64-pc-windows-msvc`)
- **Node.js 20 + pnpm 9**
- **Python 3.12 + [uv](https://docs.astral.sh/uv/)**
- **WebView2** (sudah pre-installed di Windows 11)
- **Tauri CLI** v2: `cargo install tauri-cli --version "^2.0" --locked`

```bash
# 1. Build frontend static export
cd frontend
pnpm install --frozen-lockfile
pnpm build      # → frontend/out/

# 2. Build backend sidecar exe (PyInstaller)
cd ../backend
uv sync --group package
uv run pyinstaller pyinstaller.spec --noconfirm --clean
# → backend/dist/super-aff-backend.exe

# 3. Stage sidecar untuk Tauri (rename ke target-triple)
cd ..
cp backend/dist/super-aff-backend.exe \
   src-tauri/binaries/super-aff-backend-x86_64-pc-windows-msvc.exe

# 4. Build installer NSIS via Tauri
cd src-tauri
cargo tauri build --target x86_64-pc-windows-msvc
# → src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/super-aff_<ver>_x64-setup.exe
```

Atau biarkan **GitHub Actions** yang build: tag commit `vX.Y.Z` lalu push tag — workflow `release-windows.yml` otomatis build di runner `windows-latest` dan upload installer ke Releases page.

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Tech stack

- `frontend/` — Next.js 16 (App Router) + Tailwind v4 + TypeScript, static export untuk Tauri
- `backend/` — FastAPI + httpx + Pydantic v2
- `src-tauri/` — Tauri 2 desktop shell (Rust), spawn FastAPI sidecar lewat `tauri-plugin-shell`
- `imageio-ffmpeg` — bundled ffmpeg untuk komposisi MP4 (Ken Burns zoom-pan + watermark + voice-over mux)
- Docker Compose — Caddy reverse proxy + FastAPI backend (mode server)
- PyInstaller — bundle backend FastAPI jadi single .exe (mode desktop Tauri)

## Struktur folder

```
super-aff/
├── backend/                  FastAPI server (port 8000 server / 8765 desktop)
│   ├── run_server.py         Entry point untuk PyInstaller (Tauri sidecar)
│   ├── pyinstaller.spec      Build spec yang bundle imageio-ffmpeg + uvicorn deps
│   └── app/
│       ├── main.py
│       ├── routers/          /api/shopee, /api/content, /api/voiceover, /api/compose, /api/batch
│       ├── providers/        LLM + TTS adapters (BYOK, multi-vendor)
│       │   ├── llm.py        OpenAI / Anthropic / Gemini / Groq / OpenRouter / DeepSeek / OpenAI-compat
│       │   └── tts.py        ElevenLabs / OpenAI / Gemini / MiniMax / OpenAI-compat
│       ├── shopee/           Shopee URL parser + scraper (handle shortlink + affiliate URL)
│       └── compose/          ffmpeg slideshow pipeline
├── frontend/                 Next.js 16 (port 3000 dev / 8081 docker / static-export utk Tauri)
│   ├── .env.production       NEXT_PUBLIC_API_BASE=http://127.0.0.1:8765 (untuk build Tauri)
│   └── src/
│       ├── app/              /, /single, /bulk, /settings
│       ├── components/
│       └── lib/              api.ts (fetch helpers), settings.ts (localStorage), csv.ts
├── src-tauri/                Tauri 2 desktop shell
│   ├── src/lib.rs            spawn backend sidecar + window setup
│   ├── tauri.conf.json       window/bundle config (NSIS installer)
│   ├── capabilities/         Tauri permissions (sidecar exec, dialog, process)
│   └── icons/
├── .github/workflows/
│   ├── ci.yml                lint + test pada PR
│   └── release-windows.yml   build NSIS installer di runner windows-latest
├── docker-compose.yml
└── .env.example
```

## Catatan etika & legal

Tool ini **tidak men-download ulang video produk dari seller asli** — itu pelanggaran hak cipta. Yang dipakai cuma **foto produk dari listing Shopee** (yang umumnya boleh dipakai affiliate marketer untuk promo) ditambah konten 100% baru: voice-over AI, caption AI, slideshow ffmpeg.

Tidak ada auto-upload ke Shopee. Anda upload manual via aplikasi Shopee, tetap mengikuti policy mereka.
