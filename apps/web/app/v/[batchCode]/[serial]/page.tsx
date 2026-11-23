"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { API_URL } from "@/lib/api";
import type { VerifyResult } from "@/lib/types";

const TONES = {
  red: {
    card: "border-red-300 bg-red-50 text-red-950",
    icon: "bg-red-600 text-white",
    detail: "text-red-800",
  },
  amber: {
    card: "border-amber-300 bg-amber-50 text-amber-950",
    icon: "bg-amber-500 text-white",
    detail: "text-amber-800",
  },
  green: {
    card: "border-emerald-300 bg-emerald-50 text-emerald-950",
    icon: "bg-emerald-600 text-white",
    detail: "text-emerald-800",
  },
} as const;

function VerdictIcon({ verdict }: { verdict: string }) {
  if (verdict === "REGISTERED") {
    return (
      <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (verdict === "UNUSUAL_ACTIVITY") {
    return (
      <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="2.2">
        <path d="M12 4l9 16H3L12 4z" strokeLinejoin="round" />
        <path d="M12 10v4M12 17h.01" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="2.5">
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
    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${style}`}>
      {issuer.label}
    </span>
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
          throw new Error(
            typeof body?.detail === "string"
              ? body.detail
              : `Could not check this code (${response.status})`
          );
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
    <div className="min-h-screen bg-paper">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-14 max-w-xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink text-xs font-bold text-white">
              S
            </span>
            <span className="text-sm font-semibold">Sigil</span>
          </Link>
          <span className="text-xs text-gray-500">Product check</span>
        </div>
      </header>

      <main className="mx-auto max-w-xl space-y-4 px-4 py-6">
        {loading && (
          <div className="card animate-pulse p-6">
            <div className="h-6 w-40 rounded bg-gray-200" />
            <div className="mt-3 h-4 w-64 rounded bg-gray-100" />
          </div>
        )}

        {error && !loading && (
          <div className="rounded-2xl border border-red-300 bg-red-50 p-5 text-red-950">
            <h1 className="text-lg font-bold">Could not check this code</h1>
            <p className="mt-1 text-sm text-red-800">{error}</p>
            <p className="mt-3 text-sm text-red-800">
              This does not mean the product is fake. Check the address in your
              phone's browser and try the code printed under the QR.
            </p>
          </div>
        )}

        {result && !loading && (
          <>
            <section className={`rounded-2xl border p-5 ${TONES[result.tone].card}`}>
              <div className="flex items-start gap-4">
                <span
                  className={`mt-0.5 flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${TONES[result.tone].icon}`}
                  aria-hidden
                >
                  <VerdictIcon verdict={result.verdict} />
                </span>
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-wide ${TONES[result.tone].detail}`}>
                    Scan result
                  </p>
                  <h1 className="mt-0.5 text-2xl font-bold leading-tight">
                    {result.label}
                  </h1>
                  <p className="mt-2 text-sm leading-relaxed">{result.message}</p>
                </div>
              </div>
            </section>

            {result.registered_line && (
              <section className="rounded-2xl border border-gray-200 bg-white p-5">
                <p className="text-sm font-medium leading-relaxed">
                  {result.registered_line}
                </p>
              </section>
            )}

            {result.product && Object.keys(result.product).length > 0 && (
              <section className="card overflow-hidden">
                {result.product.photo && (
                  <img
                    src={result.product.photo}
                    alt="Product"
                    className="h-48 w-full object-cover"
                  />
                )}
                <div className="p-5">
                  <h2 className="font-semibold">
                    {result.product.product_name ||
                      result.product.item_type ||
                      "Registered product"}
                  </h2>
                  <dl className="mt-4 grid gap-3 text-sm">
                    {Object.entries(result.field_labels)
                      .filter(
                        ([key]) =>
                          key !== "photo" && result.product[key] !== undefined
                      )
                      .map(([key, label]) => (
                        <div key={key} className="flex justify-between gap-4">
                          <dt className="text-gray-500">{label}</dt>
                          <dd className="text-right font-medium">
                            {result.product[key]}
                          </dd>
                        </div>
                      ))}
                  </dl>
                </div>
              </section>
            )}

            <section className="card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Producer
                  </p>
                  <p className="mt-1 font-semibold">
                    {result.issuer?.name || "Name not provided"}
                  </p>
                </div>
                <IssuerBadge issuer={result.issuer} />
              </div>
              <p className="mt-3 text-xs text-gray-500">
                Verification is carried out by Sigil's admin. It means the
                producer's documents were reviewed, not that this pack is
                genuine.
              </p>
            </section>

            {result.batch && (
              <section className="card p-5">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Registered batch
                </p>
                <dl className="mt-3 grid gap-2 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-gray-500">Batch number</dt>
                    <dd className="font-medium">{result.batch.batch_number}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-gray-500">Expiry</dt>
                    <dd className="font-medium">
                      {result.batch.expires_at ?? "No expiry"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-gray-500">Batch code</dt>
                    <dd className="font-mono text-xs">
                      {result.batch.public_code}
                    </dd>
                  </div>
                </dl>
              </section>
            )}

            {result.checklist.length > 0 && (
              <section className="card p-5">
                <h2 className="font-semibold">Compare with your pack</h2>
                <ul className="mt-3 space-y-2">
                  {result.checklist.map((item) => (
                    <li key={item} className="flex items-start gap-3 text-sm">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 rounded border-gray-300"
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-950">
              <h2 className="font-semibold">What this check cannot tell you</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5">
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
                <summary className="cursor-pointer font-medium">
                  Check this yourself
                </summary>
                <p className="mt-3 text-gray-600">
                  The batch Merkle root is stored on Solana. This code's serial
                  hashes to a leaf, and the proof below folds up to that root.
                  Anyone can recompute it.
                </p>
                <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-gray-950 p-3 text-[10px] leading-relaxed text-gray-100">
                  {JSON.stringify(result.proof, null, 2)}
                </pre>
              </details>
            )}

            <p className="px-1 text-xs leading-relaxed text-gray-500">
              This scan was logged with a coarse region and a device hash. We do
              not store your IP address or precise location, and scan records
              are deleted after 90 days. No account, no app, no wallet.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
