"use client";

import { useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { PublicKey, SystemProgram } from "@solana/web3.js";
import BN from "bn.js";
import { api, ApiError, errorMessage, API_URL } from "@/lib/api";
import { downloadWithAuth } from "@/lib/download";
import { hexToBytes, todayISO } from "@/lib/format";
import { useProgram } from "@/lib/program";
import type { Batch, Industry, Prepared } from "@/lib/types";

const STEPS = ["Industry", "Details", "Batch", "Review"];
const DRAFT_KEY = "sigil.batch.draft.v2";

type Props = {
  token: string;
  industries: Industry[];
  canCreate: boolean;
  onCreated: () => void;
};

export function BatchWizard({ token, industries, canCreate, onCreated }: Props) {
  const { publicKey } = useWallet();
  const program = useProgram();

  const [step, setStep] = useState(0);
  const [industryId, setIndustryId] = useState(industries[0]?.id ?? "");
  const [details, setDetails] = useState<Record<string, string>>({});
  const [units, setUnits] = useState("10");
  const [manufacturedAt, setManufacturedAt] = useState(todayISO());
  const [expiresAt, setExpiresAt] = useState("");
  const [uploading, setUploading] = useState<string | null>(null);
  const [signing, setSigning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState<Batch | null>(null);
  const [downloading, setDownloading] = useState(false);

  const industry =
    industries.find((item) => item.id === industryId) ?? industries[0];

  const detailManufactured = details.manufacture_date;
  const detailExpiry = details.expiry_date;
  const effectiveManufacturedAt = detailManufactured || manufacturedAt;
  const effectiveExpiresAt = detailExpiry || expiresAt || "";

  useEffect(() => {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return;
    try {
      const draft = JSON.parse(raw);
      if (typeof draft.industryId === "string") setIndustryId(draft.industryId);
      if (draft.details && typeof draft.details === "object") setDetails(draft.details);
      if (typeof draft.units === "string") setUnits(draft.units);
      if (typeof draft.manufacturedAt === "string") setManufacturedAt(draft.manufacturedAt);
      if (typeof draft.expiresAt === "string") setExpiresAt(draft.expiresAt);
    } catch {
      // ignore a broken draft
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({ industryId, details, units, manufacturedAt, expiresAt })
    );
  }, [industryId, details, units, manufacturedAt, expiresAt]);

  if (!industry) {
    return (
      <section className="card p-5">
        <p className="text-sm text-gray-600">No industry packs are loaded.</p>
      </section>
    );
  }

  function chooseIndustry(id: string) {
    if (id === industryId) return;
    setIndustryId(id);
    setDetails({});
    setExpiresAt("");
    setFieldErrors({});
    setError(null);
  }

  async function uploadPhoto(key: string, file: File) {
    setUploading(key);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api<{ url: string }>("/api/v1/uploads/photo", {
        token,
        form,
      });
      setDetails((current) => ({ ...current, [key]: result.url }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUploading(null);
    }
  }

  function advance() {
    setError(null);
    setFieldErrors({});
    if (step === 0) {
      setStep(1);
      return;
    }
    if (step === 1) {
      const missing = industry.fields.filter(
        (field) => field.required && !(details[field.key] ?? "").trim()
      );
      if (missing.length) {
        setError(`Fill in: ${missing.map((field) => field.label).join(", ")}`);
        return;
      }
      setStep(2);
      return;
    }
    if (step === 2) {
      const parsed = Number(units);
      if (!Number.isInteger(parsed) || parsed < 1 || parsed > 100_000) {
        setError("Units must be a whole number between 1 and 100,000.");
        return;
      }
      if (!effectiveManufacturedAt) {
        setError("Manufacture date is required.");
        return;
      }
      if (industry.expiry_required && !effectiveExpiresAt) {
        setError(`${industry.name} batches need an expiry date.`);
        return;
      }
      if (effectiveExpiresAt && effectiveExpiresAt <= effectiveManufacturedAt) {
        setError("Expiry must be after the manufacture date.");
        return;
      }
      setStep(3);
    }
  }

  async function signAndCreate() {
    if (!program || !publicKey) return;
    setSigning(true);
    setError(null);
    setFieldErrors({});
    try {
      const prepared = await api<Prepared>("/api/v1/batches/prepare", {
        token,
        body: {
          industry: industry.id,
          details,
          units: Number(units),
          manufactured_at: effectiveManufacturedAt,
          expires_at: effectiveExpiresAt || null,
        },
      });

      const methods = program.methods as any;
      const signature = await methods
        .createBatch(
          new BN(prepared.nonce),
          prepared.industry_code,
          Array.from(hexToBytes(prepared.merkle_root)),
          Array.from(hexToBytes(prepared.details_hash)),
          prepared.units,
          new BN(prepared.manufactured_at),
          new BN(prepared.expires_at)
        )
        .accounts({
          issuer: new PublicKey(prepared.issuer_pda),
          authority: publicKey,
          batch: new PublicKey(prepared.batch_pda),
          systemProgram: SystemProgram.programId,
        })
        .rpc();

      const batch = await api<Batch>(
        `/api/v1/batches/${prepared.batch_id}/confirm`,
        { token, body: { tx_signature: signature } }
      );
      setConfirmed(batch);
      setStep(4);
      localStorage.removeItem(DRAFT_KEY);
      onCreated();
    } catch (err) {
      if (err instanceof ApiError && err.errors && !Array.isArray(err.errors)) {
        setFieldErrors(err.errors);
      }
      setError(errorMessage(err));
    } finally {
      setSigning(false);
    }
  }

  async function downloadPdf() {
    if (!confirmed) return;
    setDownloading(true);
    try {
      await downloadWithAuth(
        confirmed.labels_pdf,
        token,
        `sigil-${confirmed.public_code}.pdf`
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDownloading(false);
    }
  }

  if (!canCreate) {
    return (
      <section className="card p-5">
        <h2 className="text-lg font-semibold">Create a batch</h2>
        <p className="mt-2 text-sm text-gray-600">
          Batch creation unlocks when an admin verifies your producer profile.
        </p>
      </section>
    );
  }

  if (step === 4 && confirmed) {
    return (
      <section className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Batch registered</h2>
            <p className="hint mt-1">
              {confirmed.units} labels are ready. The code is live on-chain.
            </p>
          </div>
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
            Active
          </span>
        </div>

        <div className="mt-4 rounded-xl bg-gray-50 p-4 text-sm">
          <p className="font-medium">
            {confirmed.details.product_name || confirmed.details.item_type}
          </p>
          <p className="mt-1 text-gray-600">
            Batch {confirmed.details.batch_number || confirmed.public_code} ·{" "}
            {confirmed.industry_name} · {confirmed.units} units · expiry{" "}
            {confirmed.expires_at ?? "none"}
          </p>
          <p className="mt-2 break-all font-mono text-xs text-gray-500">
            {confirmed.verify_base}/&lt;serial&gt;
          </p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button className="btn-primary" onClick={downloadPdf} disabled={downloading}>
            {downloading ? "Preparing…" : "Download label sheet (PDF)"}
          </button>
          <a
            className="btn-secondary"
            href={`https://explorer.solana.com/tx/${confirmed.tx_signature}?cluster=devnet`}
            target="_blank"
            rel="noreferrer"
          >
            View transaction
          </a>
        </div>

        <LabelPreview batchId={confirmed.id} token={token} />

        <div className="mt-5 flex gap-3">
          <button
            className="btn-secondary"
            onClick={() => {
              setConfirmed(null);
              setStep(0);
              setDetails({});
              setUnits("10");
              setExpiresAt("");
            }}
          >
            Create another batch
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      </section>
    );
  }

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Create a batch</h2>
        <span className="hint">Step {step + 1} of 4 · {STEPS[step]}</span>
      </div>

      <div className="mt-4 flex gap-1.5">
        {STEPS.map((label, index) => (
          <div
            key={label}
            className={`h-1.5 flex-1 rounded-full ${
              index <= step ? "bg-ink" : "bg-gray-200"
            }`}
          />
        ))}
      </div>

      <div className="mt-5">
        {step === 0 && (
          <div className="grid gap-3 sm:grid-cols-2">
            {industries.map((item) => (
              <button
                key={item.id}
                onClick={() => chooseIndustry(item.id)}
                className={`rounded-xl border p-4 text-left transition ${
                  item.id === industryId
                    ? "border-ink bg-gray-50 ring-1 ring-ink"
                    : "border-gray-200 hover:border-gray-400"
                }`}
              >
                <p className="font-semibold">{item.name}</p>
                <p className="hint mt-1">
                  {item.fields.length} fields
                  {item.expiry_required ? " · expiry required" : ""}
                </p>
              </button>
            ))}
          </div>
        )}

        {step === 1 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {industry.fields.map((field) => (
              <div
                key={field.key}
                className={field.type === "photo" ? "sm:col-span-2" : ""}
              >
                <label className="label">
                  {field.label}
                  {field.required && <span className="text-red-600"> *</span>}
                </label>
                {field.type === "photo" ? (
                  <div className="flex flex-wrap items-center gap-4">
                    {details[field.key] && (
                      <img
                        src={details[field.key]}
                        alt="Product"
                        className="h-24 w-24 rounded-xl border border-gray-200 object-cover"
                      />
                    )}
                    <input
                      type="file"
                      accept="image/*"
                      className="text-sm"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void uploadPhoto(field.key, file);
                      }}
                    />
                    {uploading === field.key && (
                      <span className="hint">Uploading…</span>
                    )}
                  </div>
                ) : (
                  <input
                    className="field"
                    type={field.type === "date" ? "date" : "text"}
                    inputMode={field.type === "number" ? "decimal" : undefined}
                    value={details[field.key] ?? ""}
                    onChange={(event) =>
                      setDetails((current) => ({
                        ...current,
                        [field.key]: event.target.value,
                      }))
                    }
                  />
                )}
                {fieldErrors[field.key] && (
                  <p className="mt-1 text-xs text-red-700">
                    {fieldErrors[field.key]}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {step === 2 && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Units</label>
              <input
                className="field"
                type="number"
                min={1}
                max={100000}
                value={units}
                onChange={(event) => setUnits(event.target.value)}
              />
              <p className="hint mt-1">
                One QR label per unit. The cap is 100,000.
              </p>
            </div>
            <div>
              <label className="label">Manufacture date</label>
              {detailManufactured ? (
                <>
                  <p className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm">
                    {detailManufactured}
                  </p>
                  <p className="hint mt-1">
                    Taken from the product details above, so the batch and the
                    pack show the same date.
                  </p>
                </>
              ) : (
                <input
                  className="field"
                  type="date"
                  value={manufacturedAt}
                  onChange={(event) => setManufacturedAt(event.target.value)}
                />
              )}
            </div>
            <div>
              <label className="label">
                Expiry date
                {industry.expiry_required ? (
                  <span className="text-red-600"> *</span>
                ) : (
                  <span className="text-gray-400"> (optional)</span>
                )}
              </label>
              {detailExpiry ? (
                <>
                  <p className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm">
                    {detailExpiry}
                  </p>
                  <p className="hint mt-1">
                    Taken from the product details above.
                  </p>
                </>
              ) : (
                <input
                  className="field"
                  type="date"
                  value={expiresAt}
                  onChange={(event) => setExpiresAt(event.target.value)}
                />
              )}
              <p className="hint mt-1">
                After this date, every scan shows Expired.
              </p>
            </div>
            {fieldErrors.units && (
              <p className="text-xs text-red-700">{fieldErrors.units}</p>
            )}
            {fieldErrors.expires_at && (
              <p className="text-xs text-red-700">{fieldErrors.expires_at}</p>
            )}
          </div>
        )}

        {step === 3 && (
          <div>
            <div className="rounded-xl border border-gray-200 p-4">
              <p className="text-sm font-semibold">
                {details.product_name || details.item_type || "Product"}
              </p>
              <p className="hint mt-1">
                {industry.name} · {units} units · made {effectiveManufacturedAt} · expires{" "}
                {effectiveExpiresAt || "never"}
              </p>
              <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                {industry.fields
                  .filter((field) => field.type !== "photo")
                  .map((field) => (
                    <div key={field.key}>
                      <dt className="text-gray-500">{field.label}</dt>
                      <dd className="font-medium">{details[field.key] || "—"}</dd>
                    </div>
                  ))}
              </dl>
              {details.photo && (
                <img
                  src={details.photo}
                  alt="Product"
                  className="mt-4 h-24 w-24 rounded-xl object-cover"
                />
              )}
            </div>
            <div className="mt-4 rounded-xl bg-gray-50 p-4 text-sm text-gray-700">
              Two things happen when you sign:
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>
                  The server generates {units} unique serials and a Merkle tree.
                </li>
                <li>
                  Your wallet commits the root, details hash, expiry and unit
                  count on-chain. After that, none of it can be edited.
                </li>
                <li>
                  Your wallet pays a small rent deposit for the batch account,
                  so it needs a little SOL.
                </li>
              </ul>
            </div>
            {fieldErrors && Object.keys(fieldErrors).length > 0 && (
              <ul className="mt-3 space-y-1 text-sm text-red-700">
                {Object.entries(fieldErrors).map(([key, value]) => (
                  <li key={key}>
                    {key}: {value}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {error && <p className="mt-4 text-sm text-red-700">{error}</p>}

      <div className="mt-6 flex items-center justify-between gap-3">
        <button
          className="btn-secondary"
          onClick={() => {
            setError(null);
            setStep(Math.max(0, step - 1));
          }}
          disabled={step === 0 || signing}
        >
          Back
        </button>
        {step < 3 ? (
          <button className="btn-primary" onClick={advance}>
            Continue
          </button>
        ) : (
          <button
            className="btn-primary"
            onClick={signAndCreate}
            disabled={signing || !program}
          >
            {signing ? "Waiting for wallet…" : "Sign and register batch"}
          </button>
        )}
      </div>
    </section>
  );
}

function LabelPreview({ batchId, token }: { batchId: number; token: string }) {
  const [labels, setLabels] = useState<{ serial: string; src: string }[]>([]);

  useEffect(() => {
    let cancelled = false;
    const urls: string[] = [];
    (async () => {
      try {
        const result = await api<{ serials: string[] }>(
          `/api/v1/batches/${batchId}/serials?limit=6`,
          { token }
        );
        const items = await Promise.all(
          result.serials.map(async (serial) => {
            const response = await fetch(
              `${API_URL}/api/v1/batches/${batchId}/labels/${serial}.png`,
              { headers: { Authorization: `Bearer ${token}` } }
            );
            if (!response.ok) return null;
            const url = URL.createObjectURL(await response.blob());
            urls.push(url);
            return { serial, src: url };
          })
        );
        if (!cancelled) {
          setLabels(items.filter(Boolean) as { serial: string; src: string }[]);
        }
      } catch {
        // previews are optional
      }
    })();
    return () => {
      cancelled = true;
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [batchId, token]);

  if (labels.length === 0) return null;

  return (
    <div className="mt-5">
      <p className="text-sm font-medium">First labels</p>
      <div className="mt-2 flex flex-wrap gap-3">
        {labels.map((label) => (
          <div key={label.serial} className="text-center">
            <img
              src={label.src}
              alt={`QR for ${label.serial}`}
              className="h-24 w-24 rounded-lg border border-gray-200"
            />
            <p className="mt-1 font-mono text-[10px] text-gray-500">
              {label.serial}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
