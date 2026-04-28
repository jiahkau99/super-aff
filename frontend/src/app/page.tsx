import Link from "next/link";

export default function HomePage() {
  return (
    <div className="space-y-12 py-8">
      <section className="text-center space-y-4">
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
          <span className="gradient-text">Auto bikin konten</span>
          <br />
          Shopee Affiliate
        </h1>
        <p className="text-lg max-w-2xl mx-auto opacity-80">
          Dari link produk Shopee → langsung jadi <b>video slideshow</b>,{" "}
          <b>voice-over AI</b>, <b>caption</b>, dan <b>hashtag</b>. Tinggal
          download, upload manual ke akun kamu.
        </p>
        <div className="flex justify-center gap-3 pt-4">
          <Link href="/single" className="btn-primary">
            Mulai (1 produk)
          </Link>
          <Link href="/bulk" className="btn-ghost">
            Bulk CSV
          </Link>
        </div>
      </section>

      <section className="grid sm:grid-cols-3 gap-4">
        <FeatureCard
          title="Slideshow + Voice-Over"
          body="Foto produk Shopee + zoom-pan Ken Burns + voice-over AI bahasa Indonesia. Format 720×1280 portrait siap upload."
        />
        <FeatureCard
          title="Caption + Hashtag"
          body="LLM bikin caption gaya viral marketplace + 25 hashtag relevan otomatis. Pilih provider sendiri (BYOK)."
        />
        <FeatureCard
          title="Bulk CSV"
          body="Upload CSV banyak produk → output ZIP berisi MP4 + caption + hashtag per produk."
        />
      </section>

      <section className="card">
        <h2 className="text-xl font-bold mb-2">Cara mulai</h2>
        <ol className="list-decimal pl-5 space-y-2 opacity-90">
          <li>
            Buka <Link className="underline" href="/settings">Settings</Link>{" "}
            dan tempel API key untuk LLM (caption) + TTS (voice-over).
          </li>
          <li>
            Buka <Link className="underline" href="/single">Single</Link> atau{" "}
            <Link className="underline" href="/bulk">Bulk</Link>.
          </li>
          <li>Paste link Shopee atau isi judul + upload foto manual.</li>
          <li>Klik <b>Generate</b>, tunggu, download MP4 + caption + hashtag.</li>
          <li>Upload manual ke aplikasi Shopee kamu.</li>
        </ol>
      </section>

      <section className="card text-sm opacity-80">
        <p>
          <b>Catatan etis:</b> super-aff <b>tidak</b> mendownload ulang video
          produk dari seller asli — itu pelanggaran hak cipta. Yang kita pakai
          cuma foto produk dari listing Shopee + voice-over AI + caption AI.
          Tidak ada auto-upload — kamu post manual mengikuti policy Shopee.
        </p>
      </section>
    </div>
  );
}

function FeatureCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="card">
      <h3 className="font-bold mb-1">{title}</h3>
      <p className="text-sm opacity-80">{body}</p>
    </div>
  );
}
