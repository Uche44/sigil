"use client";

import { useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { PublicKey, SystemProgram } from "@solana/web3.js";
import { api, errorMessage } from "@/lib/api";
import { hexToBytes, shortWallet, statusTone } from "@/lib/format";
import { useProgram } from "@/lib/program";
import type { Config, Me } from "@/lib/types";

type Props = {
  me: Me;
  token: string;
  config: Config | null;
  onChanged: () => void;
};

export function CompanyProfile({ me, token, config, onChanged }: Props) {
  const { publicKey } = useWallet();
  const program = useProgram();

  const [name, setName] = useState(me.profile?.name ?? "");
  const [country, setCountry] = useState(me.profile?.country ?? "");
  const [regulatorName, setRegulatorName] = useState(
    Object.keys(me.profile?.regulator_numbers ?? {})[0] ?? "NAFDAC"
  );
  const [regulatorNumber, setRegulatorNumber] = useState(
    Object.values(me.profile?.regulator_numbers ?? {})[0] ?? ""
  );
  const [documents, setDocuments] = useState(
    (me.profile?.documents ?? []).join("\n")
  );
  const [contactEmail, setContactEmail] = useState(
    me.profile?.contact_email ?? ""
  );
  const [busy, setBusy] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!me.profile) return;
    setName(me.profile.name);
    setCountry(me.profile.country);
    setContactEmail(me.profile.contact_email);
    setDocuments(me.profile.documents.join("\n"));
    const entries = Object.entries(me.profile.regulator_numbers);
    if (entries.length) {
      setRegulatorName(entries[0][0]);
      setRegulatorNumber(entries[0][1]);
    }
  }, [me.profile]);

  async function submit() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const regulator_numbers: Record<string, string> = {};
      if (regulatorName.trim() && regulatorNumber.trim()) {
        regulator_numbers[regulatorName.trim()] = regulatorNumber.trim();
      }
      await api("/api/v1/issuers", {
        token,
        body: {
          name: name.trim(),
          country: country.trim(),
          regulator_numbers,
          documents: documents
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
          contact_email: contactEmail.trim(),
        },
      });
      setMessage("Profile saved.");
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function registerOnChain() {
    if (!program || !publicKey || !config || !me.name_hash) return;
    setRegistering(true);
    setError(null);
    setMessage(null);
    try {
      const methods = program.methods as any;
      await methods
        .registerIssuer(Array.from(hexToBytes(me.name_hash)))
        .accounts({
          registry: new PublicKey(config.registry_pda),
          authority: publicKey,
          issuer: new PublicKey(me.issuer_pda),
          systemProgram: SystemProgram.programId,
        })
        .rpc();
      setMessage("Producer registered on-chain. Waiting for admin verification.");
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRegistering(false);
    }
  }

  const tone = statusTone(me.status);

  return (
    <section className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Company</p>
          <h2 className="mt-1.5 text-xl font-extrabold tracking-tight">
            Company profile
          </h2>
          <p className="hint mt-1.5">
            Your profile is hashed and committed on-chain. It cannot be edited
            after registration.
          </p>
        </div>
        <span
          className={`pill border ${tone}`}
        >
          {me.registered ? me.status_label : "Not registered"}
        </span>
      </div>

      {!me.profile ? (
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label">Company name</label>
            <input
              className="field"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Acme Pharma Ltd"
            />
          </div>
          <div>
            <label className="label">Country</label>
            <input
              className="field"
              value={country}
              onChange={(event) => setCountry(event.target.value)}
              placeholder="Nigeria"
            />
          </div>
          <div>
            <label className="label">Contact email</label>
            <input
              className="field"
              value={contactEmail}
              onChange={(event) => setContactEmail(event.target.value)}
              placeholder="quality@acme.example"
            />
          </div>
          <div>
            <label className="label">Regulator</label>
            <input
              className="field"
              value={regulatorName}
              onChange={(event) => setRegulatorName(event.target.value)}
              placeholder="NAFDAC"
            />
          </div>
          <div>
            <label className="label">Registration number</label>
            <input
              className="field"
              value={regulatorNumber}
              onChange={(event) => setRegulatorNumber(event.target.value)}
              placeholder="01-2345"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Document links</label>
            <textarea
              className="field min-h-24"
              value={documents}
              onChange={(event) => setDocuments(event.target.value)}
              placeholder={"One link per line\nhttps://…/licence.pdf"}
            />
            <p className="hint mt-1">
              Links to your licence, registration certificate or company
              documents. The admin reviews these before verifying you.
            </p>
          </div>
          <div className="sm:col-span-2 flex items-center gap-3">
            <button className="btn-primary" onClick={submit} disabled={busy || !name.trim()}>
              {busy ? "Saving…" : "Submit profile"}
            </button>
            {message && <span className="text-sm text-emerald-700">{message}</span>}
            {error && <span className="text-sm text-red-700">{error}</span>}
          </div>
        </div>
      ) : (
        <div className="mt-5">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-gray-500">Name</dt>
              <dd className="font-medium">{me.profile.name}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Country</dt>
              <dd className="font-medium">{me.profile.country || "—"}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Regulator numbers</dt>
              <dd className="font-medium">
                {Object.entries(me.profile.regulator_numbers)
                  .map(([key, value]) => `${key}: ${value}`)
                  .join(", ") || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Wallet</dt>
              <dd className="font-mono text-xs">{shortWallet(me.wallet, 6)}</dd>
            </div>
            {me.profile.documents.length > 0 && (
              <div className="sm:col-span-2">
                <dt className="text-gray-500">Documents</dt>
                <dd className="mt-1 space-y-1">
                  {me.profile.documents.map((doc) => (
                    <a
                      key={doc}
                      href={doc}
                      target="_blank"
                      rel="noreferrer"
                      className="block truncate text-sm text-blue-700 underline"
                    >
                      {doc}
                    </a>
                  ))}
                </dd>
              </div>
            )}
          </dl>

          {!me.registered && (
            <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm text-amber-900">
                Profile saved. Sign one transaction to register this wallet as a
                producer.
              </p>
              <button
                className="btn-primary mt-3"
                onClick={registerOnChain}
                disabled={registering || !program}
              >
                {registering ? "Waiting for wallet…" : "Sign registration"}
              </button>
            </div>
          )}

          {me.registered && me.status === 0 && (
            <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              Your registration is pending. An admin must verify your documents
              before you can create a batch.
            </p>
          )}

          {me.registered && me.status === 2 && (
            <p className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
              This producer is suspended. Existing batches show a suspended
              warning to shoppers.
            </p>
          )}

          {me.registered && me.status === 1 && (
            <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
              Verified. You can create batches below.
            </p>
          )}
        </div>
      )}

      {message && me.profile && (
        <p className="mt-4 text-sm text-emerald-700">{message}</p>
      )}
      {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
    </section>
  );
}
