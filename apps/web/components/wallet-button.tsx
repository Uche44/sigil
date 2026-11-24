"use client";

import dynamic from "next/dynamic";

const WalletMultiButtonDynamic = dynamic(
  () =>
    import("@solana/wallet-adapter-react-ui").then(
      (module) => module.WalletMultiButton
    ),
  {
    ssr: false,
    loading: () => (
      <span className="inline-block h-10 w-32 animate-pulse rounded-full bg-lav-100" />
    ),
  }
);

export function WalletButton() {
  return <WalletMultiButtonDynamic />;
}
