import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sigil — check what a product is registered as",
  description:
    "Scan a product code and see what it is registered to, whether it is expired or recalled, and how to check the pack in your hand. No app, no wallet, no account.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
