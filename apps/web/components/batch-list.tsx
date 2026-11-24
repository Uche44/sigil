"use client";

import { useCallback, useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { PublicKey } from "@solana/web3.js";
import { api, errorMessage } from "@/lib/api";
import { downloadWithAuth } from "@/lib/download";
import { useProgram } from "@/lib/program";
import type { Activity, Batch } from "@/lib/types";

type Props = {
  token: string;
  refreshKey: number;
  onChanged: () => void;
};

const STATUS_STYLES: Record<string, string> = {
  draft: "border-gray-200 bg-gray-50 text-gray-700",
  active: "border-emerald-200 bg-emerald-50 text-emerald-800",
  recalled: "border-red-200 bg-red-50 text-red-800",
};

export function BatchList({ token, refreshKey, onChanged }: Props) {
  const { publicKey } = useWallet();
  const program = useProgram();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [activity, setActivity] = useState<Record<number, Activity>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api<{ batches: Batch[] }>("/api/v1/batches", { token });
      setBatches(result.batches);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function toggleActivity(batch: Batch) {
    if (activity[batch.id]) {
      setActivity((current) => {
        const next = { ...current };
        delete next[batch.id];
        return next;
      });
      return;
    }
    try {
      const detail = await api<Batch>(`/api/v1/batches/${batch.id}`, { token });
      if (detail.activity) {
        setActivity((current) => ({ ...current, [batch.id]: detail.activity! }));
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function downloadLabels(batch: Batch) {
    setBusy(batch.id);
    try {
      await downloadWithAuth(
        batch.labels_pdf,
        token,
        `sigil-${batch.public_code}.pdf`
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function recall(batch: Batch) {
    if (!program || !publicKey) return;
    if (
      !window.confirm(
        "Recall this batch? Every future scan will show Recalled, and this cannot be undone."
      )
    ) {
      return;
    }
    setBusy(batch.id);
    setError(null);
    try {
      const prepared = await api<{
        issuer: string;
        batch: string;
      }>(`/api/v1/batches/${batch.id}/recall/prepare`, {
        token,
        method: "POST",
      });
      const methods = program.methods as any;
      await methods
        .recallBatch(1)
        .accounts({
          issuer: new PublicKey(prepared.issuer),
          authority: publicKey,
          batch: new PublicKey(prepared.batch),
        })
        .rpc();
      await api(`/api/v1/batches/${batch.id}/recall/confirm`, {
        token,
        body: { reason: 1 },
      });
      await load();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-extrabold tracking-tight">Batches</h2>
        <button className="btn-secondary" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      {loading && <p className="mt-4 text-sm text-gray-500">Loading…</p>}
      {!loading && batches.length === 0 && (
        <p className="mt-4 text-sm text-gray-500">
          No batches yet. Create one above.
        </p>
      )}

      <div className="mt-4 space-y-3">
        {batches.map((batch) => (
          <article key={batch.id} className="rounded-2xl border border-[#eee8f7] bg-[#fbf9ff] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold">
                  {batch.details.product_name || batch.details.item_type || "Product"}
                </p>
                <p className="hint mt-1">
                  {batch.industry_name} · {batch.units} units · expiry{" "}
                  {batch.expires_at ?? "none"}
                </p>
                <p className="mt-1 font-mono text-xs text-gray-500">
                  {batch.public_code}
                </p>
              </div>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${
                  STATUS_STYLES[batch.status] ?? STATUS_STYLES.draft
                }`}
              >
                {batch.status}
              </span>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {batch.status !== "draft" && (
                <button
                  className="btn-secondary"
                  onClick={() => void downloadLabels(batch)}
                  disabled={busy === batch.id}
                >
                  Labels PDF
                </button>
              )}
              <button className="btn-secondary" onClick={() => void toggleActivity(batch)}>
                {activity[batch.id] ? "Hide activity" : "Activity"}
              </button>
              {batch.status === "active" && (
                <button
                  className="btn-danger"
                  onClick={() => void recall(batch)}
                  disabled={busy === batch.id || !program}
                >
                  Recall batch
                </button>
              )}
              {batch.tx_signature && (
                <a
                  className="btn-secondary"
                  href={`https://explorer.solana.com/tx/${batch.tx_signature}?cluster=devnet`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Transaction
                </a>
              )}
            </div>

            {activity[batch.id] && (
              <div className="mt-3 rounded-2xl bg-lav-50 p-4 text-sm">
                <p>
                  {activity[batch.id].scans} scans ·{" "}
                  {activity[batch.id].scanned_serials} units scanned
                  {activity[batch.id].batch_alert && (
                    <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
                      Batch alert
                    </span>
                  )}
                </p>
                <p className="mt-2 text-gray-600">
                  {Object.entries(activity[batch.id].by_verdict)
                    .map(([verdict, count]) => `${verdict}: ${count}`)
                    .join(" · ") || "No scans yet."}
                </p>
                {activity[batch.id].flagged_serials.length > 0 && (
                  <p className="mt-2 text-gray-600">
                    Codes seen in more than one place:{" "}
                    {activity[batch.id].flagged_serials
                      .map((item) => `${item.serial} (${item.regions})`)
                      .join(", ")}
                  </p>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
