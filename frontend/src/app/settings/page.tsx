"use client";

import { useState } from "react";
import {
  testLlm,
  testShopee,
  testTts,
  type LLMCreds,
  type LLMProvider,
  type TTSCreds,
  type TTSProvider,
} from "@/lib/api";
import { BackButton } from "@/components/BackButton";
import {
  clearLLMCreds,
  clearShopeeCookie,
  clearTTSCreds,
  loadLLMCreds,
  loadShopeeCookie,
  loadTTSCreds,
  saveLLMCreds,
  saveShopeeCookie,
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

interface TestState {
  loading: boolean;
  ok: boolean | null;
  message: string;
}

const IDLE_TEST: TestState = { loading: false, ok: null, message: "" };

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
  const [shopeeCookie, setShopeeCookie] = useState<string>(() => loadShopeeCookie());
  const [savedNote, setSavedNote] = useState<string | null>(null);

  const [llmTest, setLlmTest] = useState<TestState>(IDLE_TEST);
  const [ttsTest, setTtsTest] = useState<TestState>(IDLE_TEST);
  const [shopeeTest, setShopeeTest] = useState<TestState>(IDLE_TEST);

  const llmCfg = LLM_PROVIDERS.find((p) => p.id === llm.provider)!;
  const ttsCfg = TTS_PROVIDERS.find((p) => p.id === tts.provider)!;

  function handleSave() {
    if (llm.api_key.trim()) saveLLMCreds(llm);
    if (tts.api_key.trim()) saveTTSCreds(tts);
    saveShopeeCookie(shopeeCookie);
    setSavedNote("Tersimpan di browser.");
    setTimeout(() => setSavedNote(null), 2500);
  }

  function handleClear() {
    clearLLMCreds();
    clearTTSCreds();
    clearShopeeCookie();
    setLLM({ provider: "openai", api_key: "", model: "", base_url: "" });
    setTTS({ provider: "elevenlabs", api_key: "", model: "", voice: "", base_url: "" });
    setShopeeCookie("");
    setLlmTest(IDLE_TEST);
    setTtsTest(IDLE_TEST);
    setShopeeTest(IDLE_TEST);
    setSavedNote("Settings dihapus.");
    setTimeout(() => setSavedNote(null), 2500);
  }

  async function handleTestLlm() {
    if (!llm.api_key.trim()) {
      setLlmTest({ loading: false, ok: false, message: "Isi API key dulu." });
      return;
    }
    setLlmTest({ loading: true, ok: null, message: "Lagi tes…" });
    try {
      const r = await testLlm(llm);
      setLlmTest({ loading: false, ok: r.ok, message: r.message });
    } catch (e) {
      setLlmTest({ loading: false, ok: false, message: String(e) });
    }
  }

  async function handleTestTts() {
    if (!tts.api_key.trim()) {
      setTtsTest({ loading: false, ok: false, message: "Isi API key dulu." });
      return;
    }
    setTtsTest({ loading: true, ok: null, message: "Lagi tes…" });
    try {
      const r = await testTts(tts);
      setTtsTest({ loading: false, ok: r.ok, message: r.message });
    } catch (e) {
      setTtsTest({ loading: false, ok: false, message: String(e) });
    }
  }

  async function handleTestShopee() {
    setShopeeTest({ loading: true, ok: null, message: "Lagi tes…" });
    try {
      const r = await testShopee(
        "https://shopee.co.id/product/15/100",
        shopeeCookie,
      );
      setShopeeTest({ loading: false, ok: r.ok, message: r.message });
    } catch (e) {
      setShopeeTest({ loading: false, ok: false, message: String(e) });
    }
  }

  return (
    <div className="space-y-6">
      <BackButton />
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="opacity-80 text-sm">
          API key & cookie disimpan <b>hanya di browser</b> kamu (localStorage).
          Tidak pernah dikirim ke server super-aff selain saat memang
          dibutuhkan untuk panggil provider / Shopee.
        </p>
      </header>

      <section className="card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-lg">LLM — caption + hashtag + script</h2>
          <TestButton
            state={llmTest}
            onClick={handleTestLlm}
            label="Test koneksi"
          />
        </div>
        <Field label="Provider">
          <select
            className="input"
            value={llm.provider}
            onChange={(e) => {
              setLLM({ ...llm, provider: e.target.value as LLMProvider });
              setLlmTest(IDLE_TEST);
            }}
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
            onChange={(e) => {
              setLLM({ ...llm, api_key: e.target.value });
              setLlmTest(IDLE_TEST);
            }}
          />
        </Field>
        <Field label="Model (opsional)">
          <input
            type="text"
            className="input"
            value={llm.model || ""}
            placeholder="kosongin = pakai default"
            onChange={(e) => {
              setLLM({ ...llm, model: e.target.value });
              setLlmTest(IDLE_TEST);
            }}
          />
        </Field>
        {llmCfg.needsBaseUrl && (
          <Field label="Base URL">
            <input
              type="text"
              className="input"
              value={llm.base_url || ""}
              placeholder="https://your-endpoint/v1"
              onChange={(e) => {
                setLLM({ ...llm, base_url: e.target.value });
                setLlmTest(IDLE_TEST);
              }}
            />
          </Field>
        )}
      </section>

      <section className="card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-lg">TTS — voice-over MP3</h2>
          <TestButton
            state={ttsTest}
            onClick={handleTestTts}
            label="Test suara"
          />
        </div>
        <Field label="Provider">
          <select
            className="input"
            value={tts.provider}
            onChange={(e) => {
              setTTS({ ...tts, provider: e.target.value as TTSProvider });
              setTtsTest(IDLE_TEST);
            }}
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
            onChange={(e) => {
              setTTS({ ...tts, api_key: e.target.value });
              setTtsTest(IDLE_TEST);
            }}
          />
        </Field>
        <Field label="Model (opsional)">
          <input
            type="text"
            className="input"
            value={tts.model || ""}
            placeholder="kosongin = pakai default"
            onChange={(e) => {
              setTTS({ ...tts, model: e.target.value });
              setTtsTest(IDLE_TEST);
            }}
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
            onChange={(e) => {
              setTTS({ ...tts, voice: e.target.value });
              setTtsTest(IDLE_TEST);
            }}
          />
        </Field>
        {ttsCfg.needsBaseUrl && (
          <Field label="Base URL">
            <input
              type="text"
              className="input"
              value={tts.base_url || ""}
              placeholder="https://your-endpoint/v1"
              onChange={(e) => {
                setTTS({ ...tts, base_url: e.target.value });
                setTtsTest(IDLE_TEST);
              }}
            />
          </Field>
        )}
      </section>

      <section className="card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-lg">Shopee Cookie (opsional, untuk anti-bot)</h2>
          <TestButton
            state={shopeeTest}
            onClick={handleTestShopee}
            label="Test cookie"
          />
        </div>
        <p className="opacity-80 text-sm">
          Shopee sering blokir scraping server-side. Tempelkan cookie dari
          browser kamu yang sudah login Shopee untuk naikin tingkat
          keberhasilan. Cara dapatnya:
        </p>
        <ol className="list-decimal pl-5 text-sm opacity-90 space-y-1">
          <li>
            Buka <b>shopee.co.id</b> di Chrome, login akun kamu.
          </li>
          <li>
            Tekan <b>F12</b> → tab <b>Application</b> → <b>Storage</b> →{" "}
            <b>Cookies</b> → klik <b>shopee.co.id</b>.
          </li>
          <li>
            Copy semua cookie sebagai satu baris{" "}
            <code className="opacity-80">nama=value; nama=value; ...</code>{" "}
            (atau buka tab <b>Network</b> → request manapun ke shopee →
            header <code>Cookie:</code>).
          </li>
          <li>
            Paste di kotak bawah → Save → klik <b>Test cookie</b>.
          </li>
        </ol>
        <Field label="Cookie">
          <textarea
            className="input font-mono text-xs"
            rows={4}
            value={shopeeCookie}
            placeholder="SPC_EC=...; SPC_F=...; SPC_U=...; csrftoken=...; ..."
            onChange={(e) => {
              setShopeeCookie(e.target.value);
              setShopeeTest(IDLE_TEST);
            }}
          />
        </Field>
        <p className="opacity-70 text-xs">
          ⚠️ Cookie ini setara akses ke akun Shopee kamu. Jangan share. Kalau
          mau revoke, ganti password Shopee → cookie lama auto-invalid.
        </p>
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

function TestButton({
  state,
  onClick,
  label,
}: {
  state: TestState;
  onClick: () => void;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={state.loading}
        className="btn-ghost text-sm whitespace-nowrap"
      >
        {state.loading ? "Tes…" : label}
      </button>
      {state.ok === true && (
        <span
          className="text-xs px-2 py-0.5 rounded bg-green-500/15 text-green-700 dark:text-green-400"
          title={state.message}
        >
          ✓ OK
        </span>
      )}
      {state.ok === false && (
        <span
          className="text-xs px-2 py-0.5 rounded bg-red-500/15 text-red-700 dark:text-red-400 max-w-xs truncate"
          title={state.message}
        >
          ✗ {state.message.slice(0, 60)}
          {state.message.length > 60 ? "…" : ""}
        </span>
      )}
    </div>
  );
}
