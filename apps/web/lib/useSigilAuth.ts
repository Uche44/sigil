"use client";

import { useCallback, useEffect, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import bs58 from "bs58";
import { api, ApiError, errorMessage } from "./api";
import type { Me } from "./types";

export function useSigilAuth() {
  const { publicKey, signMessage } = useWallet();
  const [token, setTokenState] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const storageKey = publicKey
    ? `sigil.token.${publicKey.toBase58()}`
    : null;

  const remember = useCallback(
    (value: string | null) => {
      setTokenState(value);
      if (!storageKey) return;
      if (value) localStorage.setItem(storageKey, value);
      else localStorage.removeItem(storageKey);
    },
    [storageKey]
  );

  useEffect(() => {
    if (!storageKey) {
      setTokenState(null);
      setMe(null);
      return;
    }
    setTokenState(localStorage.getItem(storageKey));
  }, [storageKey]);

  const refresh = useCallback(
    async (activeToken?: string | null) => {
      const value = activeToken ?? token;
      if (!value) return;
      try {
        setMe(await api<Me>("/api/v1/issuers/me", { token: value }));
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          remember(null);
          setMe(null);
        } else {
          setError(errorMessage(err));
        }
      }
    },
    [token, remember]
  );

  useEffect(() => {
    if (token) void refresh(token);
  }, [token, refresh]);

  const signIn = useCallback(async () => {
    if (!publicKey) throw new Error("Connect a wallet first.");
    if (!signMessage) throw new Error("This wallet cannot sign messages.");
    setBusy(true);
    setError(null);
    try {
      const wallet = publicKey.toBase58();
      const challenge = await api<{ nonce: string; message: string }>(
        "/api/v1/auth/nonce",
        { body: { wallet } }
      );
      const signature = await signMessage(
        new TextEncoder().encode(challenge.message)
      );
      const result = await api<{ token: string; issuer: Me }>(
        "/api/v1/auth/verify",
        {
          body: {
            wallet,
            nonce: challenge.nonce,
            signature: bs58.encode(signature),
          },
        }
      );
      remember(result.token);
      setMe(result.issuer);
    } catch (err) {
      setError(errorMessage(err));
      throw err;
    } finally {
      setBusy(false);
    }
  }, [publicKey, signMessage, remember]);

  const signOut = useCallback(() => {
    remember(null);
    setMe(null);
  }, [remember]);

  return {
    token,
    me,
    busy,
    error,
    signIn,
    signOut,
    refresh,
    clearError: () => setError(null),
  };
}
