"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  type BatchPlanItem,
  batchPlan,
  blobToBase64,
  composeSlideshow,
  fetchAsBase64,
  generateContent,
  generateVoiceover,
} from "@/lib/api";
import { BackButton } from "@/components/BackButton";
import {
  loadLLMCreds,
  loadShopeeCookie,
  loadTTSCreds,
} from "@/lib/settings";

interface BatchResult {
  index: number;
  title: string;
  ok: boolean;
  error?: string;
  videoBlob?: Blob;
  caption?: string;
  hashtags?: string[];
  voiceoverScript?: string;
}

export default function BulkPage() {
  const [csvText, setCsvText] = useState("");
  const [planItems, setPlanItems] = useState<BatchPlanItem[] | null>(null);
  const [planning, setPlanning] = useState(false);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<BatchResult[]>([]);
  const [progress, setProgress] = useState({ done: 0, total: 0, label: "" });
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [watermark, setWatermark] = useState("");
  const [tone, setTone] = useState("santai-promosi");
  const [burnSubtitle, setBurnSubtitle] = useState(true);

  const parsedRows = useMemo(() => parseCsv(csvText), [csvText]);

  async function handlePlan() {
    setGlobalError(null);
    setPlanItems(null);
    setResults([]);
    if (parsedRows.length === 0) {
      setGlobalError("CSV kosong atau tidak ada baris valid.");
      return;
    }
    setPlanning(true);
    try {
      const r = await batchPlan(parsedRows, { cookie: loadShopeeCookie() });
      setPlanItems(r.items);
    } catch (e) {
      setGlobalError(e instanceof Error ? e.message : String(e));
    } finally {
      setPlanning(false);
    }
  }

  async function handleRun() {
    if (!planItems) return;
    const llm = loadLLMCreds();
    const tts = loadTTSCreds();
    if (!llm || !llm.api_key) {
      setGlobalError(
        "Belum ada LLM key. Buka Settings dulu untuk tempel key.",
      );
      return;
    }

    setRunning(true);
    setGlobalError(null);
    setResults([]);
    setProgress({ done: 0, total: planItems.length, label: "" });

    const out: BatchResult[] = [];
    for (let i = 0; i < planItems.length; i++) {
      const item = planItems[i];
      const label = `[${i + 1}/${planItems.length}] ${item.title || "(tanpa judul)"}`;
      setProgress({ done: i, total: planItems.length, label });
      if (!item.ok || !item.title) {
        out.push({
          index: i,
          title: item.title || "(kosong)",
          ok: false,
          error: item.error || "Baris tidak valid.",
        });
        setResults([...out]);
        continue;
      }
      try {
        const c = await generateContent({
          title: item.title,
          description: item.description,
          price: item.price,
          tone,
          creds: llm,
        });
        let audioB64: string | null = null;
        if (tts && tts.api_key) {
          const audioBlob = await generateVoiceover({
            text: c.voiceover_script,
            creds: tts,
          });
          audioB64 = await blobToBase64(audioBlob);
        }
        const imagesB64: string[] = [];
        for (const u of item.images) {
          try {
            imagesB64.push(await fetchAsBase64(u));
          } catch (e) {
            console.warn("skip image", u, e);
          }
        }
        if (imagesB64.length === 0) {
          throw new Error(
            "Tidak ada foto yang berhasil di-fetch (URL Shopee mungkin di-block CORS).",
          );
        }
        const videoBlob = await composeSlideshow({
          title: item.title,
          images_b64: imagesB64,
          audio_b64: audioB64,
          caption: c.caption,
          watermark_text: watermark,
          subtitle_text: burnSubtitle ? c.voiceover_script : "",
        });
        out.push({
          index: i,
          title: item.title,
          ok: true,
          videoBlob,
          caption: c.caption,
          hashtags: c.hashtags,
          voiceoverScript: c.voiceover_script,
        });
      } catch (e) {
        out.push({
          index: i,
          title: item.title,
          ok: false,
          error: e instanceof Error ? e.message : String(e),
        });
      }
      setResults([...out]);
    }
    setProgress({ done: planItems.length, total: planItems.length, label: "Selesai" });
    setRunning(false);
  }

  return (
    <div className="space-y-6">
      <BackButton />
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Bulk CSV</h1>
        <p className="opacity-80 text-sm">
          Kolom yang dipakai (case-insensitive): <code>url</code>,{" "}
          <code>judul</code>, <code>deskripsi</code>. Kalau <code>url</code>{" "}
          terisi, kolom lain auto-scrape.
        </p>
      </header>

      <section className="card space-y-3">
        <h2 className="font-bold">1. Paste CSV</h2>
        <textarea
          className="input font-mono text-sm"
          rows={8}
          value={csvText}
          onChange={(e) => setCsvText(e.target.value)}
          placeholder={`url,judul,deskripsi\nhttps://shopee.co.id/product/111/222,,\n,Celana Jeans Skinny,Bahan melar nyaman`}
        />
        <div className="flex gap-2 items-center">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              setCsvText(await f.text());
            }}
          />
          <span className="text-sm opacity-70">
            {parsedRows.length} baris terdeteksi
          </span>
        </div>
      </section>

      <section className="card space-y-3">
        <h2 className="font-bold">2. Plan (resolve produk dari URL)</h2>
        <button
          onClick={handlePlan}
          className="btn-ghost"
          disabled={parsedRows.length === 0 || planning}
        >
          {planning ? <Spinner /> : "Plan"}
        </button>
        {planItems && (
          <div className="overflow-x-auto">
            <table className="text-sm w-full">
              <thead>
                <tr className="text-left opacity-70">
                  <th className="py-1">No</th>
                  <th>Judul</th>
                  <th>Foto</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {planItems.map((it, i) => (
                  <tr key={i} className="border-t border-black/5 dark:border-white/10">
                    <td className="py-1.5">{i + 1}</td>
                    <td className="py-1.5">{it.title || "—"}</td>
                    <td className="py-1.5">{it.images.length}</td>
                    <td className="py-1.5">
                      {it.ok ? "OK" : <span className="text-rose-600">{it.error}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card space-y-3">
        <h2 className="font-bold">3. Style</h2>
        <Field label="Watermark text (opsional)">
          <input
            type="text"
            className="input"
            value={watermark}
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

      <section className="card space-y-3">
        <h2 className="font-bold">4. Run batch</h2>
        <p className="text-sm opacity-80">
          Tiap produk diproses berurutan di browser kamu (bukan server) supaya
          API key tetap aman. Pastikan key sudah di{" "}
          <Link href="/settings" className="underline">
            Settings
          </Link>
          .
        </p>
        <button
          onClick={handleRun}
          className="btn-primary"
          disabled={!planItems || running}
        >
          {running ? (
            <>
              <Spinner /> {progress.label} ({progress.done}/{progress.total})
            </>
          ) : (
            "Run batch"
          )}
        </button>
        {globalError && (
          <div className="text-sm text-rose-700 dark:text-rose-300 bg-rose-100/60 dark:bg-rose-900/30 p-3 rounded-md">
            {globalError}
          </div>
        )}
      </section>

      {results.length > 0 && (
        <section className="card space-y-3">
          <h2 className="font-bold">5. Hasil</h2>
          <div className="space-y-3">
            {results.map((r) => (
              <ResultRow key={r.index} r={r} />
            ))}
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

function ResultRow({ r }: { r: BatchResult }) {
  const captionWithTags =
    (r.caption || "") +
    (r.hashtags && r.hashtags.length
      ? "\n\n" + r.hashtags.map((h) => `#${h}`).join(" ")
      : "");
  const filename = slug(r.title);
  return (
    <div className="border border-black/10 dark:border-white/10 rounded-lg p-3 space-y-2">
      <div className="font-medium">
        #{r.index + 1} — {r.title}
      </div>
      {r.ok ? (
        <div className="flex flex-wrap gap-2 items-center">
          {r.videoBlob && (
            <a
              href={URL.createObjectURL(r.videoBlob)}
              download={`${filename}.mp4`}
              className="btn-ghost"
            >
              MP4
            </a>
          )}
          <button
            className="btn-ghost"
            onClick={() => downloadText(`${filename}.caption.txt`, captionWithTags)}
          >
            caption.txt
          </button>
          <button
            className="btn-ghost"
            onClick={() =>
              downloadText(`${filename}.script.txt`, r.voiceoverScript || "")
            }
          >
            script.txt
          </button>
          <button
            className="btn-ghost"
            onClick={() => navigator.clipboard.writeText(captionWithTags)}
          >
            Copy caption
          </button>
        </div>
      ) : (
        <div className="text-sm text-rose-700 dark:text-rose-300">
          Gagal: {r.error}
        </div>
      )}
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

function downloadText(name: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
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

// ---- CSV parsing (minimal RFC4180-ish) ------------------------------------

function parseCsv(text: string): { url: string; judul: string; deskripsi: string }[] {
  const rows = csvRows(text);
  if (rows.length === 0) return [];
  const header = rows[0].map((h) => h.trim().toLowerCase());
  const idxUrl = header.indexOf("url");
  const idxJudul =
    header.indexOf("judul") >= 0 ? header.indexOf("judul") : header.indexOf("title");
  const idxDesc =
    header.indexOf("deskripsi") >= 0
      ? header.indexOf("deskripsi")
      : header.indexOf("description");
  const out: { url: string; judul: string; deskripsi: string }[] = [];
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    if (row.length === 0 || row.every((c) => !c.trim())) continue;
    out.push({
      url: idxUrl >= 0 ? (row[idxUrl] || "").trim() : "",
      judul: idxJudul >= 0 ? (row[idxJudul] || "").trim() : "",
      deskripsi: idxDesc >= 0 ? (row[idxDesc] || "").trim() : "",
    });
  }
  return out;
}

function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuote = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuote) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          inQuote = false;
        }
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      inQuote = true;
    } else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else if (ch === "\r") {
      // skip
    } else {
      cell += ch;
    }
  }
  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}
