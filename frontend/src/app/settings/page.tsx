"use client";

import { useState } from "react";
import type { LLMCreds, LLMProvider, TTSCreds, TTSProvider } from "@/lib/api";
import {
  clearLLMCreds,
  clearTTSCreds,
  loadLLMCreds,
  loadTTSCreds,
  saveLLMCreds,
  saveTTSCreds,
} from "@/lib/settings";

const LLM_PROVIDERS: { id: LLMProvider; label: string; needsBaseUrl: boolean }[] = [
  { id: "openai", label: "OpenAI", needsBaseUrl: false },
  { id: "anthropic", label: "Anthropic (Claude)", needsBaseUrl: false },
  { id: "gemini", label: "Google Gemini", needsBaseUrl: false },
  { id: "groq", label: "Groq", needsBaseUrl: false },
  { id: "openrouter", label: "OpenRouter", needsBaseUrl: false },
  { id: "deepseek", label: "DeepSeek", needsBaseUrl: false },
  { id: "openai_compatible", label: "OpenAI-compatible (custom)", needsBaseUrl: true },
];

const TTS_PROVIDERS: { id: TTSProvider; label: string; needsBaseUrl: boolean }[] = [
  { id: "elevenlabs", label: "ElevenLabs", needsBaseUrl: false },
  { id: "openai", label: "OpenAI TTS", needsBaseUrl: false },
  { id: "gemini", label: "Google Gemini TTS", needsBaseUrl: false },
  { id: "minimax", label: "MiniMax T2A (Indonesian)", needsBaseUrl: false },
  { id: "openai_compatible", label: "OpenAI-compatible (custom)", needsBaseUrl: true },
];

export default function SettingsPage() {
  const [llm, setLLM] = useState<LLMCreds>(
    () =>
      loadLLMCreds() || {
        provider: "openai",
        api_key: "",
        model: "",
        base_url: "",
      },
  );
  const [tts, setTTS] = useState<TTSCreds>(
    () =>
      loadTTSCreds() || {
        provider: "elevenlabs",
        api_key: "",
        model: "",
        voice: "",
        base_url: "",
      },
  );
  const [savedNote, setSavedNote] = useState<string | null>(null);

  const llmCfg = LLM_PROVIDERS.find((p) => p.id === llm.provider)!;
  const ttsCfg = TTS_PROVIDERS.find((p) => p.id === tts.provider)!;

  function handleSave() {
    if (llm.api_key.trim()) saveLLMCreds(llm);
    if (tts.api_key.trim()) saveTTSCreds(tts);
    setSavedNote("Tersimpan di browser.");
    setTimeout(() => setSavedNote(null), 2500);
  }

  function handleClear() {
    clearLLMCreds();
    clearTTSCreds();
    setLLM({ provider: "openai", api_key: "", model: "", base_url: "" });
    setTTS({ provider: "elevenlabs", api_key: "", model: "", voice: "", base_url: "" });
    setSavedNote("Settings dihapus.");
    setTimeout(() => setSavedNote(null), 2500);
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="opacity-80 text-sm">
          API key disimpan <b>hanya di browser</b> kamu (localStorage). Tidak
          pernah dikirim ke server super-aff selain saat memang dibutuhkan untuk
          panggil provider.
        </p>
      </header>

      <section className="card space-y-4">
        <h2 className="font-bold text-lg">LLM — untuk caption + hashtag + script</h2>
        <Field label="Provider">
          <select
            className="input"
            value={llm.provider}
            onChange={(e) =>
              setLLM({ ...llm, provider: e.target.value as LLMProvider })
            }
          >
            {LLM_PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="API Key">
          <input
            type="password"
            className="input"
            value={llm.api_key}
            placeholder="sk-..."
            onChange={(e) => setLLM({ ...llm, api_key: e.target.value })}
          />
        </Field>
        <Field label="Model (opsional)">
          <input
            type="text"
            className="input"
            value={llm.model || ""}
            placeholder="kosongin = pakai default"
            onChange={(e) => setLLM({ ...llm, model: e.target.value })}
          />
        </Field>
        {llmCfg.needsBaseUrl && (
          <Field label="Base URL">
            <input
              type="text"
              className="input"
              value={llm.base_url || ""}
              placeholder="https://your-endpoint/v1"
              onChange={(e) => setLLM({ ...llm, base_url: e.target.value })}
            />
          </Field>
        )}
      </section>

      <section className="card space-y-4">
        <h2 className="font-bold text-lg">TTS — untuk voice-over MP3</h2>
        <Field label="Provider">
          <select
            className="input"
            value={tts.provider}
            onChange={(e) =>
              setTTS({ ...tts, provider: e.target.value as TTSProvider })
            }
          >
            {TTS_PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="API Key">
          <input
            type="password"
            className="input"
            value={tts.api_key}
            placeholder="..."
            onChange={(e) => setTTS({ ...tts, api_key: e.target.value })}
          />
        </Field>
        <Field label="Model (opsional)">
          <input
            type="text"
            className="input"
            value={tts.model || ""}
            placeholder="kosongin = pakai default"
            onChange={(e) => setTTS({ ...tts, model: e.target.value })}
          />
        </Field>
        <Field label="Voice ID / nama (opsional)">
          <input
            type="text"
            className="input"
            value={tts.voice || ""}
            placeholder={
              tts.provider === "elevenlabs"
                ? "voice ID, mis. 21m00Tcm4TlvDq8ikWAM"
                : "alloy / Kore / dll"
            }
            onChange={(e) => setTTS({ ...tts, voice: e.target.value })}
          />
        </Field>
        {ttsCfg.needsBaseUrl && (
          <Field label="Base URL">
            <input
              type="text"
              className="input"
              value={tts.base_url || ""}
              placeholder="https://your-endpoint/v1"
              onChange={(e) => setTTS({ ...tts, base_url: e.target.value })}
            />
          </Field>
        )}
      </section>

      <div className="flex items-center gap-3">
        <button onClick={handleSave} className="btn-primary">
          Save
        </button>
        <button onClick={handleClear} className="btn-ghost">
          Clear
        </button>
        {savedNote && <span className="text-sm opacity-80">{savedNote}</span>}
      </div>

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
