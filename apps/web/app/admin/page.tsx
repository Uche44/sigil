"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletButton } from "@/components/wallet-button";
import { PublicKey, SystemProgram } from "@solana/web3.js";
import { SiteHeader } from "@/components/site-header";
import { api, errorMessage } from "@/lib/api";
import { shortWallet, statusTone } from "@/lib/format";
import { useProgram } from "@/lib/program";
import { useSigilAuth } from "@/lib/useSigilAuth";
import type { AdminIssuer, Config } from "@/lib/types";

const TABS = ["pending", "verified", "suspended", "all"] as const;
type Tab = (typeof TABS)[number];

type RegistryInfo = {
  registry_pda: string;
  exists: boolean;
  admin: string | null;
  issuer_count: number;
  wallet: string;
  wallet_is_admin: boolean;
};

export default function AdminPage() {
  const { connected, publicKey, disconnect } = useWallet();
  const auth = useSigilAuth();
  const program = useProgram();

  const [tab, setTab] = useState<Tab>("pending");
  const [issuers, setIssuers] = useState<AdminIssuer[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [registry, setRegistry] = useState<RegistryInfo | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    api<Config>("/api/v1/config").then(setConfig).catch(() => undefined);
  }, []);

  const loadRegistry = useCallback(async () => {
    if (!auth.token) return;
    try {
      setRegistry(
        await api<RegistryInfo>("/api/v1/admin/registry", { token: auth.token })
      );
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [auth.token]);

  useEffect(() => {
    void loadRegistry();
  }, [loadRegistry]);

  const load = useCallback(async () => {
    if (!auth.token) return;
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    setIssuers([]);
    try {
      const result = await api<{ issuers: AdminIssuer[] }>(
        `/api/v1/admin/issuers?status=${tab}`,
        { token: auth.token }
      );
      if (id !== requestId.current) return;
      setIssuers(result.issuers);
    } catch (err) {
      if (id !== requestId.current) return;
      setError(errorMessage(err));
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [auth.token, tab]);

  useEffect(() => {
    void load();
  }, [load]);

  async function initializeRegistry() {
    if (!program || !publicKey || !registry) return;
    setBusy("registry");
    setError(null);
    try {
      const methods = program.methods as any;
      await methods
        .initializeRegistry()
        .accounts({
          registry: new PublicKey(registry.registry_pda),
          admin: publicKey,
          systemProgram: SystemProgram.programId,
        })
        .rpc();
      await loadRegistry();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function setStatus(issuer: AdminIssuer, status: number) {
    if (!program || !publicKey || !config) return;
    setBusy(issuer.wallet);
    setError(null);
    try {
      const methods = program.methods as any;
      await methods
        .setIssuerStatus(status)
        .accounts({
          registry: new PublicKey(config.registry_pda),
          admin: publicKey,
          issuer: new PublicKey(issuer.issuer_pda),
        })
        .rpc();
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen">
      <SiteHeader right={<WalletButton />} role="admin" />

      <main className="mx-auto max-w-5xl space-y-5 px-5 py-10 sm:px-8 sm:py-12">
        <div>
          <p className="eyebrow">Admin</p>
          <h1 className="display mt-3 text-[2.6rem] sm:text-5xl">
            Producer <span className="serif">review.</span>
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-[#5f5777]">
            Verify producers and withdraw verification. The admin can never edit
            a batch, only issuer status.
          </p>
        </div>

        {!connected && (
          <section className="card p-8 text-center">
            <p className="eyebrow">Admin access</p>
            <h2 className="mt-2 text-xl font-extrabold tracking-tight">
              Connect the admin wallet
            </h2>
            <p className="mx-auto mt-2 max-w-sm text-sm text-[#6f6788]">
              Only the wallet holding the on-chain registry admin role can
              review producers.
            </p>
            <div className="mt-5 flex justify-center">
              <WalletButton />
            </div>
          </section>
        )}

        {connected && !auth.token && (
          <section className="card p-8">
            <p className="eyebrow">Admin access</p>
            <h2 className="mt-2 text-xl font-extrabold tracking-tight">Sign in</h2>
            <p className="mt-2 text-sm text-[#6f6788]">
              Sign a one-time message. No transaction and no fee.
            </p>
            <button
              className="btn-primary mt-4"
              onClick={() => void auth.signIn()}
              disabled={auth.busy}
            >
              {auth.busy ? "Waiting for wallet…" : "Sign in with wallet"}
            </button>
            {auth.error && (
              <p className="mt-3 text-sm text-red-700">{auth.error}</p>
            )}
          </section>
        )}

        {auth.token && auth.me && !auth.me.is_admin && (
          <section className="card p-6">
            <p className="text-sm text-red-700">
              This wallet is not on the admin list. Set{" "}
              <code className="rounded-md bg-lav-50 px-1.5 py-0.5">
                SIGIL_ADMIN_PUBKEYS
              </code>{" "}
              on the API to include {shortWallet(auth.me.wallet, 5)}.
            </p>
            <button
              className="btn-secondary mt-3"
              onClick={() => {
                auth.signOut();
                void disconnect();
              }}
            >
              Sign out
            </button>
          </section>
        )}

        {auth.token && auth.me?.is_admin && registry && !registry.exists && (
          <section className="card-lav p-6">
            <p className="eyebrow text-[#7b68b6]">Setup</p>
            <h2 className="mt-2 text-xl font-extrabold tracking-tight">
              Set up the registry
            </h2>
            <p className="mt-2 text-sm text-[#5f5777]">
              This program has not been initialised on this cluster. One
              transaction creates the registry and makes this wallet its admin.
            </p>
            <button
              className="btn-primary mt-4"
              onClick={() => void initializeRegistry()}
              disabled={busy === "registry" || !program}
            >
              {busy === "registry" ? "Waiting for wallet…" : "Initialize registry"}
            </button>
            {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
          </section>
        )}

        {auth.token &&
          auth.me?.is_admin &&
          registry?.exists &&
          !registry.wallet_is_admin && (
            <section className="card p-5">
              <p className="text-sm text-red-700">
                The on-chain registry admin is{" "}
                <span className="font-mono">
                  {shortWallet(registry.admin ?? "", 6)}
                </span>
                , not this wallet. Switch wallets or update
                SIGIL_ADMIN_PUBKEYS.
              </p>
            </section>
          )}

        {auth.token &&
          auth.me?.is_admin &&
          registry?.exists &&
          registry.wallet_is_admin && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="inline-flex gap-1 rounded-full border border-[#eee8f7] bg-white p-1">
                {TABS.map((item) => (
                  <button
                    key={item}
                    onClick={() => setTab(item)}
                    className={`rounded-full px-4 py-1.5 text-[12.5px] font-bold capitalize transition ${
                      tab === item
                        ? "bg-plum text-white shadow-sm"
                        : "text-[#6f6788] hover:text-ink"
                    }`}
                  >
                    {item}
                  </button>
                ))}
              </div>
              <button className="btn-secondary" onClick={() => void load()}>
                Refresh
              </button>
            </div>

            {error && (
              <p className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                {error}
              </p>
            )}
            {loading && <p className="text-sm text-[#8b83a3]">Loading…</p>}
            {!loading && issuers.length === 0 && (
              <p className="rounded-2xl border border-dashed border-[#e2daee] bg-[#fbf9ff] p-6 text-center text-sm text-[#8b83a3]">
                Nothing in this list.
              </p>
            )}

            <div className="space-y-3">
              {issuers.map((issuer) => (
                <article key={issuer.wallet} className="card p-6">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-extrabold tracking-tight">
                        {issuer.profile.name}
                      </p>
                      <p className="hint mt-1">
                        {issuer.profile.country || "No country"}
                      </p>
                      <p className="mt-1 break-all font-mono text-[11px] text-[#8b83a3]">
                        {issuer.wallet}
                      </p>
                    </div>
                    <span
                      className={`pill border ${statusTone(issuer.status)}`}
                    >
                      {issuer.status_label}
                    </span>
                  </div>

                  <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-[#8b83a3]">Regulator numbers</dt>
                      <dd className="font-medium">
                        {Object.entries(issuer.profile.regulator_numbers)
                          .map(([key, value]) => `${key}: ${value}`)
                          .join(", ") || "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[#8b83a3]">Contact</dt>
                      <dd className="font-medium">
                        {issuer.profile.contact_email || "—"}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-[#8b83a3]">Documents</dt>
                      <dd className="mt-1 space-y-1">
                        {issuer.profile.documents.length === 0 && "—"}
                        {issuer.profile.documents.map((doc) => (
                          <a
                            key={doc}
                            href={doc}
                            target="_blank"
                            rel="noreferrer"
                            className="block truncate text-[13px] font-semibold text-violet underline decoration-violet/30"
                          >
                            {doc}
                          </a>
                        ))}
                      </dd>
                    </div>
                  </dl>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {issuer.status === 0 && (
                      <button
                        className="btn-primary"
                        onClick={() => void setStatus(issuer, 1)}
                        disabled={busy === issuer.wallet || !program}
                      >
                        {busy === issuer.wallet ? "Waiting…" : "Verify producer"}
                      </button>
                    )}
                    {issuer.status === 1 && (
                      <button
                        className="btn-danger"
                        onClick={() => void setStatus(issuer, 2)}
                        disabled={busy === issuer.wallet || !program}
                      >
                        Suspend producer
                      </button>
                    )}
                    {issuer.status === 2 && (
                      <button
                        className="btn-primary"
                        onClick={() => void setStatus(issuer, 1)}
                        disabled={busy === issuer.wallet || !program}
                      >
                        Restore verification
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
