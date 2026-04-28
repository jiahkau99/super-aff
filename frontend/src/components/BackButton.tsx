"use client";

import { useRouter } from "next/navigation";

/**
 * "← Kembali" button shown at the top of subpages.
 *
 * Click handler decides at click time whether to navigate to a fallback or
 * call `router.back()`. We deliberately don't read `window.history.length`
 * during render — that would either be a `useEffect`/`setState` cascade
 * (which the lint rule forbids) or break SSR — so we just always offer a
 * working button and choose the action when the user clicks.
 */
export function BackButton({
  fallbackHref = "/",
  label = "Kembali",
}: {
  fallbackHref?: string;
  label?: string;
}) {
  const router = useRouter();

  function handleClick() {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push(fallbackHref);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="inline-flex items-center gap-1 text-sm rounded-md px-2 py-1 -ml-2 hover:bg-black/5 dark:hover:bg-white/10 opacity-80 hover:opacity-100"
    >
      <span aria-hidden>←</span>
      <span>{label}</span>
    </button>
  );
}
