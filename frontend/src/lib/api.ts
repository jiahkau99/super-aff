// Centralised fetch helpers + types for super-aff backend.

// Resolve the API base URL.
//
// Three runtime modes:
//   1. Tauri desktop  : window.__TAURI_INTERNALS__ is present. The static
//      export is served from `tauri.localhost`, but the FastAPI sidecar
//      listens on 127.0.0.1:<TAURI_BACKEND_PORT> (default 8765). We MUST
//      target the sidecar directly — relative `/api` paths would resolve
//      against `tauri.localhost` and 404.
//   2. Docker / Caddy : NEXT_PUBLIC_API_BASE unset → default to "/api"
//      (same-origin reverse proxy).
//   3. Local dev      : NEXT_PUBLIC_API_BASE=http://localhost:8000 — direct
//      to FastAPI in `pnpm dev`.
const TAURI_BACKEND_PORT = 8765;

function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    const w = window as unknown as {
      __TAURI_INTERNALS__?: unknown;
      __TAURI__?: unknown;
    };
    if (w.__TAURI_INTERNALS__ || w.__TAURI__) {
      return `http://127.0.0.1:${TAURI_BACKEND_PORT}`;
    }
  }
  return (
    process.env.NEXT_PUBLIC_API_BASE?.trim().replace(/\/$/, "") || "/api"
  );
}

export const API_BASE = resolveApiBase();

// API_BASE may be either:
//   - "/api"            : same-origin reverse proxy (docker compose default)
//   - "http://...:8000" : direct to FastAPI in dev / Tauri sidecar
// Endpoint paths below already include the "/api/..." prefix from FastAPI
// routers, so we only join with API_BASE if it does not already end with /api.
function url(path: string): string {
  if (API_BASE.endsWith("/api")) {
    // Strip the leading "/api" from the path because API_BASE already has it.
    return API_BASE + path.replace(/^\/api/, "");
  }
  return API_BASE + path;
}

export type LLMProvider =
  | "openai"
  | "anthropic"
  | "gemini"
  | "groq"
  | "openrouter"
  | "deepseek"
  | "openai_compatible";

export type TTSProvider =
  | "elevenlabs"
  | "openai"
  | "gemini"
  | "minimax"
  | "openai_compatible";

export interface LLMCreds {
  provider: LLMProvider;
  api_key: string;
  model?: string;
  base_url?: string;
}

export interface TTSCreds {
  provider: TTSProvider;
  api_key: string;
  model?: string;
  voice?: string;
  base_url?: string;
}

export interface ShopeeProduct {
  title: string;
  description: string;
  price: number | null;
  currency: string;
  images: string[];
  rating_star: number | null;
  historical_sold: number | null;
  shop_name: string | null;
  item_id: number | null;
  shop_id: number | null;
  source_url: string | null;
}

export interface ScrapeResponse {
  ok: boolean;
  product: ShopeeProduct | null;
  error: string | null;
}

export async function scrapeShopee(productUrl: string): Promise<ScrapeResponse> {
  const r = await fetch(url("/api/shopee/scrape"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: productUrl }),
  });
  if (!r.ok) {
    const text = await r.text();
    return { ok: false, product: null, error: `HTTP ${r.status}: ${text}` };
  }
  return r.json();
}

export interface GeneratedContent {
  caption: string;
  hashtags: string[];
  voiceover_script: string;
}

export async function generateContent(payload: {
  title: string;
  description?: string;
  price?: number | null;
  extra_context?: string;
  language?: "id" | "en";
  tone?: string;
  hashtag_count?: number;
  creds: LLMCreds;
}): Promise<GeneratedContent> {
  const r = await fetch(url("/api/content/generate"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      language: "id",
      tone: "santai-promosi",
      hashtag_count: 25,
      ...payload,
    }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`Generate content gagal (${r.status}): ${text}`);
  }
  return r.json();
}

export async function generateVoiceover(payload: {
  text: string;
  creds: TTSCreds;
}): Promise<Blob> {
  const r = await fetch(url("/api/voiceover/generate"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`Voiceover gagal (${r.status}): ${text}`);
  }
  return r.blob();
}

export async function composeSlideshow(payload: {
  title: string;
  images_b64: string[];
  audio_b64?: string | null;
  caption?: string;
  watermark_text?: string;
  duration_per_image?: number;
  target_resolution?: [number, number];
}): Promise<Blob> {
  const r = await fetch(url("/api/compose/slideshow"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      caption: "",
      watermark_text: "",
      duration_per_image: 3.0,
      target_resolution: [720, 1280],
      ...payload,
    }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`Compose gagal (${r.status}): ${text}`);
  }
  return r.blob();
}

export interface BatchPlanItem {
  url: string;
  title: string;
  description: string;
  images: string[];
  price: number | null;
  ok: boolean;
  error: string | null;
}

export async function batchPlan(
  rows: { url: string; judul: string; deskripsi: string }[],
): Promise<{ items: BatchPlanItem[] }> {
  const r = await fetch(url("/api/batch/plan"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`Batch plan gagal (${r.status}): ${text}`);
  }
  return r.json();
}

// Backend health probe — used by the Tauri splash to wait until uvicorn is
// actually listening before unlocking the UI.
export async function pingBackend(signal?: AbortSignal): Promise<boolean> {
  try {
    const r = await fetch(url("/api/util/healthz"), { signal });
    return r.ok;
  } catch {
    // Fall back to the legacy /healthz path which lives at the FastAPI root.
    try {
      const base = API_BASE.endsWith("/api")
        ? API_BASE.slice(0, -4)
        : API_BASE;
      const r = await fetch(`${base}/healthz`, { signal });
      return r.ok;
    } catch {
      return false;
    }
  }
}

// ---- Browser helpers ------------------------------------------------------

// Fetch a remote (possibly cross-origin) image and return it as base64.
//
// Browser-side fetching of e.g. Shopee CDN URLs hits CORS *and* the Tauri
// CSP `connect-src` allowlist. Route through the backend, which has neither
// constraint.
export async function fetchAsBase64(imageUrl: string): Promise<string> {
  const r = await fetch(url("/api/util/fetch-image"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: imageUrl }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`Gagal download ${imageUrl}: HTTP ${r.status}: ${text}`);
  }
  const data = (await r.json()) as { image_b64: string };
  return data.image_b64;
}

export function arrayBufferToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let binary = "";
  // Process in chunks to avoid call-stack overflow on large images.
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const r = String(reader.result || "");
      // strip "data:*/*;base64," prefix
      const comma = r.indexOf(",");
      resolve(comma >= 0 ? r.slice(comma + 1) : r);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

export function fileToBase64(file: File): Promise<string> {
  return blobToBase64(file);
}
