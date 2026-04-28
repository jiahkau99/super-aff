import type { Metadata } from "next";
import "./globals.css";
import { BackendReady } from "@/components/BackendReady";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "super-aff — Auto Konten Shopee Affiliate",
  description:
    "Auto bikin slideshow + voice-over + caption + hashtag dari produk Shopee. BYOK, no auto-upload.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body className="min-h-screen antialiased">
        <BackendReady>
          <Navbar />
          <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
        </BackendReady>
      </body>
    </html>
  );
}
