import Link from "next/link";
import { SiteHeader } from "@/components/site-header";

const STEPS = [
  {
    number: "01",
    title: "A producer registers a batch",
    body: "They pick an industry, fill in its fields, set an expiry and sign one transaction from their own wallet.",
  },
  {
    number: "02",
    title: "Every unit gets its own code",
    body: "Serials are generated and a Merkle root of all of them is committed on Solana. The root cannot be changed later.",
  },
  {
    number: "03",
    title: "Anyone scans before paying",
    body: "A normal phone camera opens the check. No app, no wallet, no account, and scanning never uses the code up.",
  },
];

const INDUSTRIES = [
  { number: "01", name: "Medicine", detail: "Regulator number, manufacture and expiry dates" },
  { number: "02", name: "Cosmetics", detail: "Brand, batch number and use-by date" },
  { number: "03", name: "Food & drink", detail: "Production date, expiry and batch number" },
  { number: "04", name: "Precious materials", detail: "Weight, purity and certificate reference" },
];

const LIMITS = [
  "A QR code cannot prove which physical pack it is stuck on. A copied code on a fake of the same product looks identical.",
  "Scan-pattern hints can miss a single copy and can false-alarm on honest shoppers.",
  "Someone outside the chain decides who counts as a real producer. For now that is the admin.",
  "Tamper-evident labels matter and sit outside the software. Sigil reduces and exposes counterfeiting; it does not end it.",
];

function HeroPanel() {
  return (
    <div className="rise delay-2 relative mx-auto mt-12 max-w-5xl overflow-hidden rounded-[30px] border border-white/40 shadow-[0_40px_90px_-40px_rgba(42,35,66,0.65)]">
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(135deg, #4d3f86 0%, #7461b2 38%, #a995db 68%, #d8cdf1 100%)",
        }}
      />
      <div className="absolute -left-24 -top-24 h-80 w-80 rounded-full bg-[#c7b6f2] opacity-40 blur-3xl" />
      <div className="absolute -bottom-32 right-0 h-96 w-96 rounded-full bg-[#efe6ff] opacity-30 blur-3xl" />
      <div className="absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/15" />
      <div className="absolute left-1/2 top-1/2 h-[26rem] w-[26rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10" />

      <div className="relative grid items-center gap-8 px-6 py-10 sm:px-12 sm:py-14 md:grid-cols-[1.02fr_0.98fr]">
        <div className="rise delay-3">
          <p className="eyebrow text-white/55">A scan result</p>
          <h2 className="display mt-4 text-[2.4rem] text-white sm:text-5xl">
            Registered.
            <br />
            <span className="serif text-white/90">And that is all it claims.</span>
          </h2>
          <p className="mt-5 max-w-sm text-sm leading-relaxed text-white/75">
            What the code is registered to, who made it, when it expires, and
            whether the producer or regulator has pulled it. Then a checklist to
            compare with the pack in your hand.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {["Batch B-2026-001", "Expiry 10 Jan 2030", "Verified producer"].map(
              (label) => (
                <span
                  key={label}
                  className="rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[10.5px] font-semibold text-white/85 backdrop-blur"
                >
                  {label}
                </span>
              )
            )}
          </div>
        </div>

        <div className="relative mx-auto w-full max-w-[330px]">
          <div className="absolute -inset-8 rounded-full bg-white/10 blur-3xl" />
          <div className="relative -rotate-2 rounded-[26px] border border-white/70 bg-white p-5 shadow-[0_30px_60px_-30px_rgba(24,18,46,0.8)]">
            <div className="flex items-center justify-between gap-3">
              <span className="pill border border-emerald-200 bg-emerald-50 text-emerald-800">
                <span aria-hidden>✓</span> Registered
              </span>
              <span className="text-[9px] font-bold uppercase tracking-[0.13em] text-[#8b83a3]">
                Verified producer
              </span>
            </div>

            <div className="mt-5 flex gap-4">
              <div className="rounded-2xl border border-[#eee8f7] bg-white p-1.5">
                <img
                  src="/qr-frame.svg"
                  alt="Example QR code"
                  className="h-[86px] w-[86px]"
                />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9a92ad]">
                  Product
                </p>
                <p className="mt-1 truncate text-sm font-extrabold tracking-tight">
                  Paracetamol 500mg
                </p>
                <p className="mt-2 text-[11px] text-[#7d7595]">Batch 2026-001</p>
                <p className="text-[11px] text-[#7d7595]">Expires 10 Jan 2030</p>
              </div>
            </div>

            <div className="mt-4 rounded-xl bg-[#f6f2fd] px-3 py-2.5 text-[10.5px] leading-relaxed text-[#5f5777]">
              Compare this with the pack in your hand. Sigil never says a pack is
              genuine.
            </div>
          </div>

          <span className="absolute -bottom-3 -left-2 -rotate-3 rounded-full border border-white/60 bg-white px-3 py-1.5 text-[10px] font-bold text-plum shadow-lg sm:-left-6">
            Scanned 3 times today
          </span>
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <SiteHeader />

      <main>
        <section className="px-5 pt-14 sm:px-8 sm:pt-20">
          <div className="mx-auto max-w-4xl text-center">
            <span className="rise pill pill-lav">Open source · Solana</span>
            <h1 className="rise delay-1 display mx-auto mt-6 max-w-5xl text-[clamp(2.7rem,6.2vw,4.8rem)]">
              Know what you&rsquo;re buying,
              <br />
              <span className="serif">before</span> you pay.
            </h1>
            <p className="rise delay-2 mx-auto mt-6 max-w-xl text-[15px] leading-relaxed text-[#5f5777] sm:text-base">
              Sigil is a product-record layer for medicine, cosmetics and
              packaged goods. Scan a label and see what the code is registered
              to — who made it, when it expires, and whether it has been recalled.
            </p>
            <div className="rise delay-2 mt-8 flex flex-wrap justify-center gap-3">
              <Link className="btn-primary" href="/producer">
                Register a product
              </Link>
              <Link className="btn-secondary" href="#how">
                How a scan works
              </Link>
            </div>
            <p className="rise delay-3 mt-5 text-[10px] font-bold tracking-[0.18em] text-[#918aa5]">
              NO APP · NO WALLET · NO ACCOUNT
            </p>
          </div>

          <HeroPanel />
        </section>

        <section className="mx-auto max-w-5xl px-5 pt-20 sm:px-8">
          <div className="grid gap-3 sm:grid-cols-3">
            {STEPS.map((step) => (
              <div key={step.number} className="rounded-2xl border border-[#eee8f7] bg-white/60 p-5">
                <div className="flex items-baseline gap-3">
                  <span className="serif text-2xl text-lav-500">{step.number}</span>
                  <h2 className="text-sm font-extrabold tracking-tight">{step.title}</h2>
                </div>
                <p className="mt-3 text-[12.5px] leading-relaxed text-[#6f6788]">
                  {step.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section id="how" className="mx-auto max-w-5xl px-5 py-20 sm:px-8">
          <div className="grid gap-8 md:grid-cols-2 md:items-end">
            <div>
              <p className="eyebrow">What Sigil is</p>
              <h2 className="display mt-4 text-4xl sm:text-[3.4rem]">
                A record, <span className="serif">not</span> a badge.
              </h2>
            </div>
            <div>
              <p className="text-sm leading-relaxed text-[#5f5777]">
                Most authenticity tools ask you to trust a sticker. Sigil
                publishes what the code is registered to and what the producer
                committed on-chain, then gives you the proof so you can check it
                without trusting the server.
              </p>
              <Link className="rule-link mt-5" href="/producer">
                See the producer flow
              </Link>
            </div>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-[1.25fr_1fr_1fr]">
            <div className="card-lav relative overflow-hidden p-6">
              <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/60 blur-2xl" />
              <p className="eyebrow text-[#7b68b6]">Live status</p>
              <h3 className="mt-3 text-xl font-extrabold tracking-tight">
                Expiry and recall are checked at scan time.
              </h3>
              <p className="mt-3 text-[13px] leading-relaxed text-[#5f5777]">
                A counterfeiter gains nothing by copying a recalled product&rsquo;s
                code. The same scan that showed Registered yesterday can show
                Recalled today.
              </p>
              <div className="mt-6 space-y-2">
                {[
                  ["●", "Registered", "text-emerald-800 bg-emerald-50 border-emerald-200"],
                  ["!", "Unusual activity", "text-amber-800 bg-amber-50 border-amber-200"],
                  ["×", "Recalled", "text-red-800 bg-red-50 border-red-200"],
                ].map(([icon, label, style]) => (
                  <span
                    key={label}
                    className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-bold ${style}`}
                  >
                    <span className="grid h-4 w-4 place-items-center rounded-full bg-white/70 text-[9px]">
                      {icon}
                    </span>
                    {label}
                  </span>
                ))}
              </div>
            </div>

            <div className="card-dark p-6">
              <p className="eyebrow text-white/45">Shopper side</p>
              <h3 className="mt-3 text-xl font-extrabold tracking-tight text-white">
                No app. No wallet. No account.
              </h3>
              <p className="mt-3 text-[13px] leading-relaxed text-white/65">
                A normal camera opens a web page. Scanning never consumes the
                code, so a browsing shopper cannot &ldquo;use up&rdquo; the pack for
                the next person.
              </p>
              <p className="mt-6 font-serif text-2xl italic text-lav-200">
                Eleven scans later, it still works.
              </p>
            </div>

            <div className="card-dark p-6">
              <p className="eyebrow text-white/45">The commitment</p>
              <h3 className="mt-3 text-xl font-extrabold tracking-tight text-white">
                One root, many units.
              </h3>
              <p className="mt-3 text-[13px] leading-relaxed text-white/65">
                Serials live in a Merkle tree. Only the root is stored on-chain,
                so the server cannot invent a valid serial after the batch is
                signed.
              </p>
              <p className="mt-6 font-mono text-[10px] leading-relaxed text-white/50">
                sha256(&ldquo;sigil:leaf:v1&rdquo; ‖ batch ‖ serial)
              </p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-5 pb-20 sm:px-8">
          <div className="grid gap-8 md:grid-cols-[0.9fr_1.1fr]">
            <div>
              <p className="eyebrow">Industry packs</p>
              <h2 className="display mt-4 text-4xl sm:text-[3.4rem]">
                One engine.
                <br />
                <span className="serif">Many</span> industries.
              </h2>
              <p className="mt-4 max-w-sm text-sm leading-relaxed text-[#5f5777]">
                Each pack is a JSON file with required fields and shopper copy.
                Adding an industry needs no code change — medicine, cosmetics and
                food all run through the same record and verification engine.
              </p>
              <Link className="rule-link mt-5" href="/producer">
                Create a batch
              </Link>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {INDUSTRIES.map((industry, index) => (
                <div
                  key={industry.name}
                  className={`rounded-2xl border p-5 ${
                    index === 0
                      ? "border-[#d9ccf2] bg-[#eee7fb]"
                      : "border-[#eee8f7] bg-white"
                  }`}
                >
                  <span className="serif text-2xl text-lav-500">{industry.number}</span>
                  <h3 className="mt-3 text-sm font-extrabold tracking-tight">
                    {industry.name}
                  </h3>
                  <p className="mt-1.5 text-[11.5px] leading-relaxed text-[#7d7595]">
                    {industry.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-5 pb-20 sm:px-8">
          <div className="card-dark overflow-hidden rounded-[30px] p-8 sm:p-10">
            <div className="grid gap-10 md:grid-cols-[0.95fr_1.05fr]">
              <div>
                <p className="eyebrow text-white/40">The honest part</p>
                <h2 className="display mt-4 text-3xl text-white sm:text-[2.8rem]">
                  What a scan
                  <br />
                  <span className="serif text-lav-200">cannot</span> prove.
                </h2>
                <p className="mt-5 max-w-xs text-sm leading-relaxed text-white/60">
                  Sigil is deliberately careful about what it claims. These
                  limits are in the README, the product copy and the pitch.
                </p>
              </div>
              <ul className="space-y-4">
                {LIMITS.map((limit, index) => (
                  <li key={limit} className="flex gap-4 border-t border-white/10 pt-4 first:border-0 first:pt-0">
                    <span className="font-serif text-lg italic text-white/35">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <p className="text-[12.5px] leading-relaxed text-white/70">
                      {limit}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-5 pb-16 sm:px-8">
          <div className="card-lav flex flex-col items-start justify-between gap-6 p-8 sm:flex-row sm:items-center sm:p-10">
            <div>
              <p className="eyebrow text-[#7b68b6]">Start here</p>
              <h2 className="display mt-3 text-3xl text-plum sm:text-4xl">
                Check the code. Then the pack.
              </h2>
              <p className="mt-3 max-w-md text-sm text-[#5f5777]">
                Register a batch, print the labels, and let anyone verify what
                the code is registered to before they pay.
              </p>
            </div>
            <Link className="btn-primary shrink-0" href="/producer">
              Producer dashboard
            </Link>
          </div>
        </section>

        <footer className="border-t border-[#eee8f7] px-5 py-8 sm:px-8">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 text-[11px] font-medium text-[#8b83a3]">
            <p>Sigil · open-source product records on Solana</p>
            <p>It never claims a pack is genuine.</p>
          </div>
        </footer>
      </main>
    </div>
  );
}
