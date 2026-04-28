"use client";

import { useEffect, useState } from "react";

import { pingBackend } from "@/lib/api";

type Phase = "checking" | "ready" | "timeout";

// In Tauri, the FastAPI sidecar is spawned right before the WebView opens.
// Uvicorn typically listens within 1–3s; we keep polling for up to ~60s and
// surface a friendly message instead of letting the user click into a fetch
// error.
const POLL_INTERVAL_MS = 500;
const TIMEOUT_MS = 60_000;

function isTauri(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as {
    __TAURI_INTERNALS__?: unknown;
    __TAURI__?: unknown;
  };
  return Boolean(w.__TAURI_INTERNALS__ || w.__TAURI__);
}

export function BackendReady({ children }: { children: React.ReactNode }) {
  // Outside Tauri we don't need a splash — Docker / dev server already control
  // backend lifecycle.
  const [enabled] = useState<boolean>(() => isTauri());
  const [phase, setPhase] = useState<Phase>(enabled ? "checking" : "ready");

  useEffect(() => {
    if (!enabled) return;
    const ctrl = new AbortController();
    const start = Date.now();
    let cancelled = false;

    async function loop() {
      while (!cancelled) {
        const ok = await pingBackend(ctrl.signal);
        if (cancelled) return;
        if (ok) {
          setPhase("ready");
          return;
        }
        if (Date.now() - start > TIMEOUT_MS) {
          setPhase("timeout");
          return;
        }
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      }
    }

    void loop();
    return () => {
      cancelled = true;
      ctrl.abort();
    };
  }, [enabled]);

  if (phase === "ready") return <>{children}</>;

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-md text-center space-y-4">
        <div className="text-2xl font-extrabold gradient-text">super-aff</div>
        {phase === "checking" ? (
          <>
            <div className="flex justify-center">
              <div
                className="h-8 w-8 rounded-full border-2 border-current border-t-transparent animate-spin"
                aria-label="Loading"
              />
            </div>
            <p className="text-sm opacity-80">
              Menyiapkan backend lokal...
              <br />
              <span className="opacity-60">
                Pertama kali boot bisa makan 2–5 detik (PyInstaller unpack).
              </span>
            </p>
          </>
        ) : (
          <>
            <p className="text-base font-semibold text-red-500">
              Backend lokal gagal start.
            </p>
            <p className="text-sm opacity-80">
              Coba tutup aplikasi dan buka lagi. Kalau masalah berulang, cek
              apakah port <code>8765</code> sudah dipakai aplikasi lain, atau
              antivirus / Windows Defender SmartScreen mem-block{" "}
              <code>super-aff-backend.exe</code>.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="btn-primary"
            >
              Coba lagi
            </button>
          </>
        )}
      </div>
    </div>
  );
}
