// localStorage-backed BYOK settings store.
// Keys are stored ONLY in the browser; never sent to the super-aff backend
// except as part of an outbound LLM/TTS call payload.

import type { LLMCreds, TTSCreds } from "./api";

const LLM_KEY = "super-aff:llm";
const TTS_KEY = "super-aff:tts";
const SHOPEE_COOKIE_KEY = "super-aff:shopee-cookie";

export function loadLLMCreds(): LLMCreds | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(LLM_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as LLMCreds;
  } catch {
    return null;
  }
}

export function saveLLMCreds(creds: LLMCreds): void {
  localStorage.setItem(LLM_KEY, JSON.stringify(creds));
}

export function clearLLMCreds(): void {
  localStorage.removeItem(LLM_KEY);
}

export function loadTTSCreds(): TTSCreds | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(TTS_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as TTSCreds;
  } catch {
    return null;
  }
}

export function saveTTSCreds(creds: TTSCreds): void {
  localStorage.setItem(TTS_KEY, JSON.stringify(creds));
}

export function clearTTSCreds(): void {
  localStorage.removeItem(TTS_KEY);
}

// Raw `Cookie:` header value pasted by the user from a logged-in Shopee
// browser session. Used by the Shopee scraper to bypass anti-bot blocks.
// Stored ONLY in localStorage; never synced anywhere.
export function loadShopeeCookie(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(SHOPEE_COOKIE_KEY) || "";
}

export function saveShopeeCookie(cookie: string): void {
  const trimmed = cookie.trim();
  if (trimmed) {
    localStorage.setItem(SHOPEE_COOKIE_KEY, trimmed);
  } else {
    localStorage.removeItem(SHOPEE_COOKIE_KEY);
  }
}

export function clearShopeeCookie(): void {
  localStorage.removeItem(SHOPEE_COOKIE_KEY);
}
