import Link from "next/link";
import { SiteHeader } from "@/components/site-header";

const STEPS = [
  {
    title: "A verified producer registers a batch",
    body: "They choose an industry, fill in its required fields, set an expiry date and sign one transaction from their own wallet.",
  },
  {
    title: "Every unit gets its own code",
    body: "The system generates one random serial per unit and commits a Merkle root of all of them on Solana.",
  },
  {
    title: "Anyone scans before paying",
    body: "A normal phone camera opens a page. No app, no wallet, no account. It shows what the code is registered to and whether the batch is expired or recalled.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-500">
          Open source · Solana · No app required
        </p>
        <h1 className="mt-3 text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          Check what a product is registered as, before you pay.
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-relaxed text-gray-700">
          Sigil is a product-record layer for fake medicine, cosmetics and other
          packaged goods. It never calls a pack genuine. It shows what the code
          is registered to, and asks you to compare that with the pack in your
          hand.
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <Link className="btn-primary" href="/producer">
            I am a producer
          </Link>
          <Link className="btn-secondary" href="/admin">
            I am an admin
          </Link>
        </div>

        <section className="mt-12 grid gap-4 sm:grid-cols-3">
          {STEPS.map((step, index) => (
            <div key={step.title} className="card p-5">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm font-bold text-white">
                {index + 1}
              </span>
              <h2 className="mt-3 font-semibold">{step.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-gray-600">
                {step.body}
              </p>
            </div>
          ))}
        </section>

        <section className="mt-10 rounded-2xl border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold">The honest limits</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-gray-700">
            <li>
              A QR code cannot prove which physical pack it is stuck on. A real
              code copied onto a fake of the same product looks identical.
            </li>
            <li>
              Scan-pattern hints can miss a single copy and can false-alarm on
              honest shoppers.
            </li>
            <li>
              Someone off-chain decides who is a real producer. For now that is
              the admin, later a regulator or trade body.
            </li>
            <li>
              Tamper-evident labels matter and are outside the software. Sigil
              reduces and exposes counterfeiting; it does not end it.
            </li>
          </ul>
        </section>

        <section className="mt-8 rounded-2xl bg-ink p-6 text-white">
          <h2 className="text-lg font-semibold">Why live status is the point</h2>
          <p className="mt-2 text-sm leading-relaxed text-gray-200">
            A shopper can check right now whether a batch is expired or recalled.
            A counterfeiter gains nothing by copying a recalled product's code.
            Authenticity signals are a secondary benefit.
          </p>
        </section>
      </main>
    </div>
  );
}
