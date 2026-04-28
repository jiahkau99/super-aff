import Link from "next/link";

export function Navbar() {
  return (
    <nav className="border-b border-black/5 dark:border-white/10 bg-white/40 dark:bg-black/20 backdrop-blur-sm sticky top-0 z-30">
      <div className="mx-auto max-w-5xl px-4 h-14 flex items-center justify-between">
        <Link href="/" className="font-bold text-lg gradient-text">
          super-aff
        </Link>
        <div className="flex items-center gap-1 text-sm">
          <Link
            href="/single"
            className="px-3 py-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/10"
          >
            Single
          </Link>
          <Link
            href="/bulk"
            className="px-3 py-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/10"
          >
            Bulk CSV
          </Link>
          <Link
            href="/settings"
            className="px-3 py-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/10"
          >
            Settings
          </Link>
        </div>
      </div>
    </nav>
  );
}
