import Link from "next/link";

export function SiteHeader({ right }: { right?: React.ReactNode }) {
  return (
    <header className="border-b border-gray-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-sm font-bold text-white">
            S
          </span>
          <span className="text-base font-semibold tracking-tight">Sigil</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm text-gray-600">
          <Link href="/producer" className="hover:text-ink">
            Producer
          </Link>
          <Link href="/admin" className="hover:text-ink">
            Admin
          </Link>
          {right}
        </nav>
      </div>
    </header>
  );
}
