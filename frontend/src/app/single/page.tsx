"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  composeSlideshow,
  fetchAsBase64,
  fileToBase64,
  generateContent,
  generateVoiceover,
  scrapeShopee,
  blobToBase64,
  type GeneratedContent,
  type ShopeeProduct,
} from "@/lib/api";
import { BackButton } from "@/components/BackButton";
import {
  loadLLMCreds,
  loadShopeeCookie,
  loadTTSCreds,
} from "@/lib/settings";

type Stage =
  | "idle"
  | "scraping"
  | "ready_to_generate"
  | "generating_content"
  | "generating_voice"
  | "composing"
  | "done"
  | "error";

interface UploadedImage {
  name: string;
  url: string; // object URL for preview
  b64: string; // base64 (no data: prefix) for backend
}

export default function SinglePage() {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState<number | null>(null);
  const [scrapedImages, setScrapedImages] = useState<string[]>([]);
  const [uploadedImages, setUploadedImages] = useState<UploadedImage[]>([]);
  const [watermark, setWatermark] = useState("");
  const [tone, setTone] = useState("santai-promosi");
  const [burnSubtitle, setBurnSubtitle] = useState(true);

  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState<GeneratedContent | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  // Load defaults
  useEffect(() => {
    return () => {
      // Cleanup object URLs on unmount
      uploadedImages.forEach((u) => URL.revokeObjectURL(u.url));
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      if (videoUrl) URL.revokeObjectURL(videoUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleScrape() {
    setError(null);
    setStage("scraping");
    setScrapedImages([]);
    try {
      const r = await scrapeShopee(url, { cookie: loadShopeeCookie() });
      if (!r.ok || !r.product) {
        setError(
          r.error ||
            "Gagal scrape. Bisa lanjut manual: isi judul + upload foto sendiri.",
        );
        setStage("idle");
        return;
      }
      const p: ShopeeProduct = r.product;
      setTitle(p.title || "");
      setDescription(p.description || "");
      setPrice(p.price);
      setScrapedImages(p.images);
      setStage("ready_to_generate");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStage("idle");
    }
  }

  async function handleUpload(files: FileList | null) {
    if (!files) return;
    const next: UploadedImage[] = [];
    for (const file of Array.from(files)) {
      if (!file.type.startsWith("image/")) continue;
      const b64 = await fileToBase64(file);
      next.push({ name: file.name, url: URL.createObjectURL(file), b64 });
    }
    setUploadedImages((prev) => [...prev, ...next]);
    if (title.trim() || next.length > 0) setStage("ready_to_generate");
  }

  function removeUploaded(idx: number) {
    setUploadedImages((prev) => {
      const removed = prev[idx];
      if (removed) URL.revokeObjectURL(removed.url);
      return prev.filter((_, i) => i !== idx);
    });
  }

  function removeScraped(idx: number) {
    setScrapedImages((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleGenerate() {
    setError(null);
    const llm = loadLLMCreds();
    const tts = loadTTSCreds();
    if (!llm || !llm.api_key) {
      setError(
        "Belum ada API key LLM. Buka Settings dulu untuk tempel key (OpenAI / Gemini / Anthropic / dll).",
      );
      return;
    }
    if (!title.trim()) {
      setError("Judul produk wajib diisi.");
      return;
    }
    if (uploadedImages.length === 0 && scrapedImages.length === 0) {
      setError("Butuh minimal 1 foto produk (upload manual atau dari scrape).");
      return;
    }

    try {
      // 1. Generate caption + hashtag + voice script
      setStage("generating_content");
      const c = await generateContent({
        title,
        description,
        price,
        tone,
        creds: llm,
      });
      setContent(c);

      // 2. Generate voice-over MP3 (optional, only if TTS configured)
      let audioB64: string | null = null;
      if (tts && tts.api_key) {
        setStage("generating_voice");
        const audioBlob = await generateVoiceover({
          text: c.voiceover_script,
          creds: tts,
        });
        const localUrl = URL.createObjectURL(audioBlob);
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setAudioUrl(localUrl);
        audioB64 = await blobToBase64(audioBlob);
      }

      // 3. Collect images. Uploaded files already have b64; scraped URLs need fetch.
      const imagesB64: string[] = [];
      for (const u of uploadedImages) imagesB64.push(u.b64);
      for (const remoteUrl of scrapedImages) {
        try {
          const b = await fetchAsBase64(remoteUrl);
          imagesB64.push(b);
        } catch (err) {
          console.warn("Skip image", remoteUrl, err);
        }
      }
      if (imagesB64.length === 0) {
        throw new Error(
          "Tidak ada gambar yang bisa diproses (semua URL Shopee gagal di-fetch). Upload manual.",
        );
      }

      // 4. Compose slideshow
      setStage("composing");
      const videoBlob = await composeSlideshow({
        title,
        images_b64: imagesB64,
        audio_b64: audioB64,
        caption: c.caption,
        watermark_text: watermark,
        duration_per_image: 3.0,
        target_resolution: [720, 1280],
        subtitle_text: burnSubtitle ? c.voiceover_script : "",
      });
      const vUrl = URL.createObjectURL(videoBlob);
      if (videoUrl) URL.revokeObjectURL(videoUrl);
      setVideoUrl(vUrl);
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStage("error");
    }
  }

  const captionWithTags = content
    ? content.caption.trim() +
      "\n\n" +
      content.hashtags.map((h) => `#${h}`).join(" ")
    : "";

  return (
    <div className="space-y-6">
      <BackButton />
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Single Product</h1>
        <p className="opacity-80 text-sm">
          Paste link Shopee untuk auto-isi, atau lewati & isi manual.
        </p>
      </header>

      {/* Step 1: Shopee URL */}
      <section className="card space-y-3">
        <h2 className="font-bold">1. Link Shopee (opsional)</h2>
        <div className="flex gap-2">
          <input
            type="text"
            className="input flex-1"
            value={url}
            placeholder="https://shopee.co.id/product/123456/789012"
            onChange={(e) => setUrl(e.target.value)}
          />
          <button
            onClick={handleScrape}
            className="btn-ghost"
            disabled={!url.trim() || stage === "scraping"}
          >
            {stage === "scraping" ? <Spinner /> : "Scrape"}
          </button>
        </div>
        {scrapedImages.length > 0 && (
          <div>
            <div className="text-sm opacity-80 mb-2">
              {scrapedImages.length} foto dari Shopee. Klik untuk hapus.
            </div>
            <ImageGrid
              urls={scrapedImages}
              onRemove={removeScraped}
            />
          </div>
        )}
      </section>

      {/* Step 2: Manual fields + upload */}
      <section className="card space-y-3">
        <h2 className="font-bold">2. Detail Produk</h2>
        <Field label="Judul produk *">
          <input
            type="text"
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>
        <Field label="Deskripsi (opsional)">
          <textarea
            className="input"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        <Field label="Harga (Rp, opsional)">
          <input
            type="number"
            className="input"
            value={price ?? ""}
            onChange={(e) =>
              setPrice(e.target.value ? Number(e.target.value) : null)
            }
          />
        </Field>
        <Field label="Upload foto (bisa lebih dari 1)">
          <input
            type="file"
            multiple
            accept="image/*"
            onChange={(e) => handleUpload(e.target.files)}
          />
        </Field>
        {uploadedImages.length > 0 && (
          <ImageGrid
            urls={uploadedImages.map((u) => u.url)}
            onRemove={removeUploaded}
          />
        )}
      </section>

      {/* Step 3: Style options */}
      <section className="card space-y-3">
        <h2 className="font-bold">3. Style</h2>
        <Field label="Watermark text (opsional, dibakar di tiap frame)">
          <input
            type="text"
            className="input"
            value={watermark}
            placeholder="mis. SAMSTORE9 atau nama toko kamu"
            onChange={(e) => setWatermark(e.target.value)}
          />
        </Field>
        <Field label="Tone caption">
          <select
            className="input"
            value={tone}
            onChange={(e) => setTone(e.target.value)}
          >
            <option value="santai-promosi">Santai promosi</option>
            <option value="hardsell-FOMO">Hardsell / FOMO</option>
            <option value="reviewer-jujur">Reviewer jujur</option>
            <option value="lucu">Lucu / receh</option>
            <option value="formal-elegan">Formal elegan</option>
          </select>
        </Field>
        <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
          <input
            type="checkbox"
            checked={burnSubtitle}
            onChange={(e) => setBurnSubtitle(e.target.checked)}
          />
          <span>Burn subtitle (hardsub) dari voice-over script ke video</span>
        </label>
      </section>

      {/* Step 4: Generate */}
      <section className="card space-y-3">
        <h2 className="font-bold">4. Generate</h2>
        <p className="text-sm opacity-80">
          Pastikan API key sudah di-set di{" "}
          <Link href="/settings" className="underline">
            Settings
          </Link>
          . LLM wajib (caption); TTS opsional (kalau gak ada, video tanpa
          voice-over).
        </p>
        <button
          onClick={handleGenerate}
          className="btn-primary"
          disabled={
            stage === "generating_content" ||
            stage === "generating_voice" ||
            stage === "composing"
          }
        >
          {stage === "generating_content" && (
            <>
              <Spinner /> Bikin caption + hashtag…
            </>
          )}
          {stage === "generating_voice" && (
            <>
              <Spinner /> Bikin voice-over…
            </>
          )}
          {stage === "composing" && (
            <>
              <Spinner /> Compose video…
            </>
          )}
          {stage !== "generating_content" &&
            stage !== "generating_voice" &&
            stage !== "composing" &&
            "Generate konten"}
        </button>
        {error && (
          <div className="text-sm text-rose-700 dark:text-rose-300 bg-rose-100/60 dark:bg-rose-900/30 p-3 rounded-md">
            {error}
          </div>
        )}
      </section>

      {/* Step 5: Results */}
      {content && (
        <section className="card space-y-4">
          <h2 className="font-bold">5. Hasil</h2>
          {videoUrl && (
            <div>
              <h3 className="font-medium mb-1">Video</h3>
              <video
                src={videoUrl}
                controls
                className="w-full max-w-xs rounded-lg border border-black/10"
              />
              <a
                href={videoUrl}
                download={`${slug(title)}.mp4`}
                className="btn-ghost inline-block mt-2"
              >
                Download MP4
              </a>
            </div>
          )}
          {audioUrl && (
            <div>
              <h3 className="font-medium mb-1">Voice-over</h3>
              <audio src={audioUrl} controls />
              <a
                href={audioUrl}
                download={`${slug(title)}.mp3`}
                className="btn-ghost inline-block ml-2"
              >
                Download MP3
              </a>
            </div>
          )}
          <div>
            <h3 className="font-medium mb-1">Caption + Hashtag</h3>
            <textarea
              className="input"
              rows={10}
              value={captionWithTags}
              readOnly
            />
            <button
              onClick={() => navigator.clipboard.writeText(captionWithTags)}
              className="btn-ghost mt-2"
            >
              Copy
            </button>
          </div>
          <div>
            <h3 className="font-medium mb-1">Voice-over script</h3>
            <textarea
              className="input"
              rows={4}
              value={content.voiceover_script}
              readOnly
            />
          </div>
        </section>
      )}

      <style jsx>{`
        .input {
          width: 100%;
          padding: 0.55rem 0.75rem;
          background: rgba(255, 255, 255, 0.7);
          border: 1px solid rgba(26, 18, 8, 0.12);
          border-radius: 0.5rem;
          font-size: 0.95rem;
        }
        :global(.dark) .input {
          background: rgba(255, 255, 255, 0.04);
          border-color: rgba(255, 255, 255, 0.12);
          color: var(--app-fg);
        }
      `}</style>
    </div>
  );
}

function ImageGrid({
  urls,
  onRemove,
}: {
  urls: string[];
  onRemove: (idx: number) => void;
}) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
      {urls.map((u, i) => (
        <button
          key={u + i}
          onClick={() => onRemove(i)}
          className="relative aspect-[3/4] rounded-md overflow-hidden border border-black/10 hover:opacity-70"
          title="Klik untuk hapus"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={u}
            alt={`foto ${i + 1}`}
            className="w-full h-full object-cover"
          />
        </button>
      ))}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium opacity-90">{label}</span>
      {children}
    </label>
  );
}

function Spinner() {
  return <span className="spinner mr-2 align-middle" />;
}

function slug(s: string): string {
  return (
    s
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 50) || "produk"
  );
}
