"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { API_URL, mediaUrl } from "@/lib/api";
import type { VerifyResult } from "@/lib/types";

const TONES = {
  red: {
    card: "border-[#efc7ce] bg-[#fbeef0] text-[#481d27]",
    icon: "bg-[#7b2739] text-white",
    detail: "text-[#8b4a57]",
    soft: "bg-white/60",
  },
  amber: {
    card: "border-[#ead6ab] bg-[#fbf3e2] text-[#4b3812]",
    icon: "bg-[#a97b20] text-white",
    detail: "text-[#8a6a25]",
    soft: "bg-white/60",
  },
  green: {
    card: "border-[#c3e2d2] bg-[#edf7f1] text-[#173d2c]",
    icon: "bg-[#2f6b4f] text-white",
    detail: "text-[#3f7a5e]",
    soft: "bg-white/60",
  },
} as const;

function VerdictIcon({ verdict }: { verdict: string }) {
  if (verdict === "REGISTERED") {
    return (
      <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.4">
        <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (verdict === "UNUSUAL_ACTIVITY") {
    return (
      <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.1">
        <path d="M12 4l9 16H3L12 4z" strokeLinejoin="round" />
        <path d="M12 10v4M12 17h.01" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.4">
      <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
    </svg>
  );
}

function IssuerBadge({ issuer }: { issuer: VerifyResult["issuer"] }) {
  if (!issuer) return null;
  const style = issuer.verified
    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
    : issuer.status === 2
      ? "border-red-200 bg-red-50 text-red-800"
      : "border-amber-200 bg-amber-50 text-amber-800";
  return (
    <span className={`rounded-full border px-2.5 py-1 text-[10.5px] font-bold ${style}`}>
      {issuer.label}
    </span>
  );
}

function ProductPhoto({ src, alt }: { src?: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  const resolved = mediaUrl(src);

  if (!resolved || failed) {
    return (
      <div className="flex h-40 items-center justify-center bg-[radial-gradient(500px_180px_at_50%_0%,#f3edfd,#e4d9f6)]">
        <span className="pill border border-white/80 bg-white/70 text-[#7b68b6]">
          No product photo
        </span>
      </div>
    );
  }

  return (
    <div className="relative h-48 w-full overflow-hidden bg-lav-50">
      <img
        src={resolved}
        alt={alt}
        className="h-full w-full object-cover"
        onError={() => setFailed(true)}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/10 to-transparent" />
    </div>
  );
}

export default function ShopperPage() {
  const params = useParams<{ batchCode: string; serial: string }>();
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const batchCode = decodeURIComponent(params.batchCode ?? "");
    const serial = decodeURIComponent(params.serial ?? "");
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(
      `${API_URL}/api/v1/verify/${encodeURIComponent(batchCode)}/${encodeURIComponent(serial)}?proof=true`,
      { cache: "no-store" }
    )
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (!response.ok) {
          const message =
            typeof body?.detail === "string"
              ? body.detail
              : body?.error === "chain unavailable"
                ? "The Solana RPC is temporarily unavailable. Try again in a moment."
                : `Could not check this code (${response.status})`;
          throw new Error(message);
        }
        if (!cancelled) setResult(body as VerifyResult);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not check this code");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params.batchCode, params.serial]);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-[#eee8f7] bg-paper/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-2xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2.5">
            <img
              src="/sigil-logo.png"
              alt=""
              className="h-8 w-8 rounded-[11px] object-cover"
            />
            <span className="text-sm font-extrabold tracking-tight">Sigil</span>
          </Link>
          <span className="pill pill-lav">Product check</span>
        </div>
      </header>

      <main className="mx-auto max-w-2xl space-y-4 px-4 py-6">
        {loading && (
          <div className="card animate-pulse p-6">
            <div className="h-7 w-44 rounded-full bg-lav-100" />
            <div className="mt-4 h-4 w-64 rounded-full bg-lav-50" />
            <div className="mt-2 h-4 w-52 rounded-full bg-lav-50" />
          </div>
        )}

        {error && !loading && (
          <div className="rounded-[24px] border border-[#efc7ce] bg-[#fbeef0] p-6 text-[#481d27]">
            <p className="eyebrow text-[#8b4a57]">Scan result</p>
            <h1 className="display mt-2 text-3xl">Could not check this code</h1>
            <p className="mt-3 text-sm leading-relaxed text-[#8b4a57]">{error}</p>
            <p className="mt-4 rounded-xl bg-white/60 p-3 text-[12.5px] leading-relaxed">
              This does not mean the product is fake. Check the address in your
              phone&rsquo;s browser and try the code printed under the QR.
            </p>
          </div>
        )}

        {result && !loading && (
          <>
            <section className={`rounded-[26px] border p-5 shadow-[0_20px_50px_-40px_rgba(32,26,53,0.7)] sm:p-6 ${TONES[result.tone].card}`}>
              <div className="flex items-start gap-4">
                <span
                  className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${TONES[result.tone].icon}`}
                  aria-hidden
                >
                  <VerdictIcon verdict={result.verdict} />
                </span>
                <div className="min-w-0">
                  <p className={`eyebrow ${TONES[result.tone].detail}`}>Scan result</p>
                  <h1 className="display mt-1 text-[2rem] leading-[1.02]">
                    {result.label}
                  </h1>
                  <p className="mt-2.5 text-[13px] leading-relaxed opacity-90">
                    {result.message}
                  </p>
                </div>
              </div>
            </section>

            {result.registered_line && (
              <section className="card p-5">
                <p className="eyebrow">The registered record</p>
                <p className="mt-2.5 text-[14px] font-medium leading-relaxed text-[#3b3452]">
                  {result.registered_line}
                </p>
              </section>
            )}

            {result.product && Object.keys(result.product).length > 0 && (
              <section className="card overflow-hidden">
                {result.product.photo ? (
                  <ProductPhoto
                    src={result.product.photo}
                    alt={result.product.product_name || "Product"}
                  />
                ) : null}
                <div className="p-5">
                  <p className="eyebrow">Registered product</p>
                  <h2 className="mt-2 text-xl font-extrabold tracking-tight">
                    {result.product.product_name ||
                      result.product.item_type ||
                      "Registered product"}
                  </h2>
                  <dl className="mt-4 divide-y divide-[#f0ebf8] text-[13px]">
                    {Object.entries(result.field_labels)
                      .filter(
                        ([key]) =>
                          key !== "photo" && result.product[key] !== undefined
                      )
                      .map(([key, label]) => (
                        <div key={key} className="flex justify-between gap-4 py-2.5">
                          <dt className="text-[#8b83a3]">{label}</dt>
                          <dd className="text-right font-bold text-[#3b3452]">
                            {result.product[key]}
                          </dd>
                        </div>
                      ))}
                  </dl>
                </div>
              </section>
            )}

            <section className="card p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Producer</p>
                  <p className="mt-2 text-lg font-extrabold tracking-tight">
                    {result.issuer?.name || "Name not provided"}
                  </p>
                </div>
                <IssuerBadge issuer={result.issuer} />
              </div>
              <p className="mt-4 rounded-xl bg-lav-50 px-3 py-2.5 text-[11.5px] leading-relaxed text-[#7d7595]">
                Verification means the producer&rsquo;s documents were reviewed
                by Sigil&rsquo;s admin. It does not mean this physical pack is
                genuine.
              </p>
            </section>

            {result.batch && (
              <section className="card p-5">
                <p className="eyebrow">Batch</p>
                <dl className="mt-3 divide-y divide-[#f0ebf8] text-[13px]">
                  <div className="flex justify-between gap-4 py-2.5">
                    <dt className="text-[#8b83a3]">Batch number</dt>
                    <dd className="font-bold">{result.batch.batch_number}</dd>
                  </div>
                  <div className="flex justify-between gap-4 py-2.5">
                    <dt className="text-[#8b83a3]">Expiry</dt>
                    <dd className="font-bold">
                      {result.batch.expires_at ?? "No expiry"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4 py-2.5">
                    <dt className="text-[#8b83a3]">Batch code</dt>
                    <dd className="rounded-md bg-lav-50 px-2 py-0.5 font-mono text-[11px] text-[#5a5274]">
                      {result.batch.public_code}
                    </dd>
                  </div>
                </dl>
              </section>
            )}

            {result.checklist.length > 0 && (
              <section className="card p-5">
                <h2 className="text-lg font-extrabold tracking-tight">
                  Compare with your pack
                </h2>
                <p className="hint mt-1">Tick only what matches your pack.</p>
                <ul className="mt-4 space-y-2">
                  {result.checklist.map((item) => (
                    <li key={item}>
                      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-[#eee8f7] bg-[#fbf9ff] p-3 text-[13px] leading-relaxed transition hover:border-[#d9ccf2]">
                        <input
                          type="checkbox"
                          className="mt-0.5 h-4 w-4 rounded border-gray-300"
                        />
                        <span>{item}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="card-dark p-5">
              <p className="eyebrow text-white/40">The honest part</p>
              <h2 className="mt-2 text-lg font-extrabold tracking-tight text-white">
                What this check cannot tell you
              </h2>
              <ul className="mt-3 space-y-2.5 text-[12px] leading-relaxed text-white/65">
                <li>
                  A QR code cannot prove which physical pack it is stuck on. A
                  copied code on a fake of the same product looks identical here.
                </li>
                <li>
                  Scan patterns are hints, not proof. One odd scan can be normal.
                </li>
                <li>
                  Someone outside the chain decides who counts as a real
                  producer.
                </li>
              </ul>
            </section>

            {result.proof && (
              <details className="card p-5 text-sm">
                <summary className="cursor-pointer font-bold">
                  Check this yourself
                </summary>
                <p className="mt-3 text-[12.5px] leading-relaxed text-[#7d7595]">
                  The batch Merkle root is stored on Solana. This code&rsquo;s
                  serial hashes to a leaf, and the proof below folds up to that
                  root. Anyone can recompute it.
                </p>
                <pre className="mt-3 max-h-80 overflow-auto rounded-xl bg-plum p-3 text-[10px] leading-relaxed text-lav-100">
                  {JSON.stringify(result.proof, null, 2)}
                </pre>
              </details>
            )}

            <p className="px-2 pb-4 text-center text-[10.5px] leading-relaxed text-[#9a92ad]">
              This scan was logged with a coarse region and a device hash. We do
              not store your IP address or precise location, and scan records are
              deleted after 90 days. No account, no app, no wallet.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
