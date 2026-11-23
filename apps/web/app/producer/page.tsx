"use client";

import { useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { SiteHeader } from "@/components/site-header";
import { CompanyProfile } from "@/components/company-profile";
import { BatchWizard } from "@/components/batch-wizard";
import { BatchList } from "@/components/batch-list";
import { api, errorMessage } from "@/lib/api";
import { shortWallet } from "@/lib/format";
import { useSigilAuth } from "@/lib/useSigilAuth";
import type { Config, Industry } from "@/lib/types";

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
      <SiteHeader right={<WalletMultiButton />} />

      <main className="mx-auto max-w-3xl space-y-5 px-4 py-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Producer dashboard
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Register your company, create a batch, print the labels. Every
            batch is committed from your own wallet. On devnet your wallet needs
            a little SOL for the rent deposit.
          </p>
        </div>

        {loadError && (
          <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {loadError}. Is the API running?
          </p>
        )}

        {!connected && (
          <section className="card p-6 text-center">
            <h2 className="text-lg font-semibold">Connect a Solana wallet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-gray-600">
              Your wallet is your producer identity. Sigil never holds your keys
              and never asks for a seed phrase.
            </p>
            <div className="mt-5 flex justify-center">
              <WalletMultiButton />
            </div>
          </section>
        )}

        {connected && publicKey && !auth.token && (
          <section className="card p-6">
            <h2 className="text-lg font-semibold">Sign in</h2>
            <p className="mt-2 text-sm text-gray-600">
              Sign a one-time message to prove this wallet is yours. It is not a
              transaction and costs no fee.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                className="btn-primary"
                onClick={() => void auth.signIn()}
                disabled={auth.busy}
              >
                {auth.busy ? "Waiting for wallet…" : "Sign in with wallet"}
              </button>
              <button
                className="btn-secondary"
                onClick={() => void disconnect()}
              >
                Disconnect
              </button>
            </div>
            {auth.error && (
              <p className="mt-3 text-sm text-red-700">{auth.error}</p>
            )}
          </section>
        )}

        {auth.token && auth.me && (
          <>
            <p className="text-sm text-gray-600">
              Signed in as{" "}
              <span className="font-mono text-xs">
                {shortWallet(auth.me.wallet, 5)}
              </span>{" "}
              <button
                className="ml-2 text-xs font-semibold underline"
                onClick={() => {
                  auth.signOut();
                  void disconnect();
                }}
              >
                Sign out
              </button>
            </p>

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

            <BatchList
              token={auth.token}
              refreshKey={refreshKey}
              onChanged={() => setRefreshKey((value) => value + 1)}
            />
          </>
        )}
      </main>
    </div>
  );
}
