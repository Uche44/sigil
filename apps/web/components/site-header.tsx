import Link from "next/link";

type Role = "public" | "producer" | "admin";

export function SiteHeader({
  right,
  role = "public",
}: {
  right?: React.ReactNode;
  role?: Role;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-[#eee8f7] bg-paper/80 backdrop-blur-xl">
      <div className="mx-auto flex h-[76px] max-w-6xl items-center justify-between gap-3 px-5 sm:px-8">
        <Link href="/" className="flex items-center gap-3">
          <img
            src="/sigil-logo.png"
            alt=""
            className="h-9 w-9 rounded-[13px] object-cover shadow-[0_10px_20px_-12px_rgba(42,35,66,0.9)]"
          />
          <span className="flex flex-col leading-none">
            <span className="text-[16px] font-extrabold tracking-[-0.03em]">
              Sigil
            </span>
            <span className="mt-1 text-[8.5px] font-bold uppercase tracking-[0.22em] text-[#9a92ad]">
              product records
            </span>
          </span>
        </Link>

        <nav className="flex items-center gap-3 sm:gap-6">
          <Link href="/#how" className="nav-link hidden sm:inline">
            How it works
          </Link>
          {role === "public" ? (
            <Link
              href="/producer"
              className="pill pill-dark px-4 py-2.5 hover:opacity-90"
            >
              For producers
            </Link>
          ) : (
            <span className="pill pill-lav capitalize">{role}</span>
          )}
          {right}
        </nav>
      </div>
    </header>
  );
}
