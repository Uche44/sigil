"use client";

import { useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletButton } from "@/components/wallet-button";
import { SiteHeader } from "@/components/site-header";
import { CompanyProfile } from "@/components/company-profile";
import { BatchWizard } from "@/components/batch-wizard";
import { BatchList } from "@/components/batch-list";
import { api, errorMessage } from "@/lib/api";
import { shortWallet } from "@/lib/format";
import { useSigilAuth } from "@/lib/useSigilAuth";
import type { Config, Industry } from "@/lib/types";

function AuthGate({
  connected,
  signIn,
  busy,
  error,
  disconnect,
}: {
  connected: boolean;
  signIn: () => void;
  busy: boolean;
  error: string | null;
  disconnect: () => void;
}) {
  return (
    <section className="mt-8 grid overflow-hidden rounded-[28px] border border-[#e7e0f2] bg-white lg:grid-cols-[1.05fr_0.95fr]">
      <div className="relative overflow-hidden bg-[linear-gradient(140deg,#4d3f86_0%,#7360b0_52%,#b7a6e4_100%)] p-8 text-white sm:p-10">
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/15 blur-2xl" />
        <div className="absolute -bottom-20 -left-10 h-56 w-56 rounded-full bg-[#d8cdf1]/30 blur-2xl" />
        <div className="relative">
          <p className="eyebrow text-white/55">Producer access</p>
          <h2 className="display mt-4 text-3xl sm:text-[2.6rem]">
            Your wallet is
            <br />
            <span className="serif text-white/90">your signature.</span>
          </h2>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/70">
            Sigil never holds your keys. You sign one message to sign in, then one
            transaction to commit each batch.
          </p>
          <ul className="mt-6 space-y-2.5 text-[12px] text-white/75">
            <li className="flex items-center gap-2">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-white/15 text-[9px]">✓</span>
              No fee to sign in
            </li>
            <li className="flex items-center gap-2">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-white/15 text-[9px]">✓</span>
              Batch fields cannot be edited after signing
            </li>
            <li className="flex items-center gap-2">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-white/15 text-[9px]">✓</span>
              Labels are generated after confirmation
            </li>
          </ul>
        </div>
      </div>

      <div className="flex flex-col justify-center p-8 sm:p-10">
        <p className="eyebrow">Start</p>
        <h3 className="mt-2 text-2xl font-extrabold tracking-tight">
          {connected ? "Sign in with your wallet" : "Connect a Solana wallet"}
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-[#6f6788]">
          {connected
            ? "Sign a one-time message to prove this wallet is yours. It is not a transaction and costs no fee."
            : "Your wallet is your producer identity. Phantom and Solflare are supported."}
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          {connected ? (
            <button className="btn-primary" onClick={signIn} disabled={busy}>
              {busy ? "Waiting for wallet…" : "Sign in with wallet"}
            </button>
          ) : (
            <WalletButton />
          )}
          {connected && (
            <button className="btn-secondary" onClick={disconnect}>
              Disconnect
            </button>
          )}
        </div>
        {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
        <p className="mt-6 text-[11px] leading-relaxed text-[#9a92ad]">
          On devnet your wallet needs a little SOL for the batch account rent.
        </p>
      </div>
    </section>
  );
}

export default function ProducerPage() {
  const { connected, publicKey, disconnect } = useWallet();
  const auth = useSigilAuth();

  const [industries, setIndustries] = useState<Industry[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    Promise.all([
      api<{ industries: Industry[] }>("/api/v1/industries"),
      api<Config>("/api/v1/config"),
    ])
      .then(([industryResult, configResult]) => {
        setIndustries(industryResult.industries);
        setConfig(configResult);
      })
      .catch((err) => setLoadError(errorMessage(err)));
  }, []);

  return (
    <div className="min-h-screen">
      <SiteHeader right={<WalletButton />} role="producer" />

      <main className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-12">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="eyebrow">Producer dashboard</p>
            <h1 className="display mt-3 text-[2.6rem] sm:text-5xl">
              Labels, records,{" "}
              <span className="serif">done.</span>
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-relaxed text-[#5f5777]">
              Register your company, commit a batch from your own wallet, and
              print one QR per unit. Every commitment is public and cannot be
              edited afterwards.
            </p>
          </div>

          {auth.token && auth.me && (
            <div className="flex items-center gap-3">
              <span
                className={`pill border ${
                  auth.me.status === 1
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : auth.me.status === 2
                      ? "border-red-200 bg-red-50 text-red-800"
                      : "border-amber-200 bg-amber-50 text-amber-800"
                }`}
              >
                {auth.me.status_label ?? "Not registered"}
              </span>
              <button
                className="btn-ghost text-xs"
                onClick={() => {
                  auth.signOut();
                  void disconnect();
                }}
              >
                Sign out
              </button>
            </div>
          )}
        </div>

        {loadError && (
          <p className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {loadError}. Is the API running?
          </p>
        )}

        {(!connected || !auth.token) && (
          <AuthGate
            connected={connected}
            signIn={() => void auth.signIn()}
            busy={auth.busy}
            error={auth.error}
            disconnect={() => void disconnect()}
          />
        )}

        {auth.token && auth.me && (
          <>
            <p className="mt-6 text-[11.5px] text-[#8b83a3]">
              Signed in as{" "}
              <span className="font-mono text-[#5a5274]">
                {shortWallet(auth.me.wallet, 5)}
              </span>
            </p>

            <div className="mt-4 grid items-start gap-5 lg:grid-cols-[0.92fr_1.08fr]">
              <CompanyProfile
                me={auth.me}
                token={auth.token}
                config={config}
                onChanged={() => {
                  void auth.refresh();
                  setRefreshKey((value) => value + 1);
                }}
              />
              <BatchWizard
                token={auth.token}
                industries={industries}
                canCreate={auth.me.status === 1}
                onCreated={() => setRefreshKey((value) => value + 1)}
              />
            </div>

            <div className="mt-5">
              <BatchList
                token={auth.token}
                refreshKey={refreshKey}
                onChanged={() => setRefreshKey((value) => value + 1)}
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
