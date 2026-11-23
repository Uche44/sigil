export function shortWallet(value: string | null | undefined, size = 4): string {
  if (!value) return "";
  if (value.length <= size * 2 + 1) return value;
  return `${value.slice(0, size)}…${value.slice(-size)}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "No expiry";
  return value;
}

export function hexToBytes(hex: string): Uint8Array {
  const clean = hex.startsWith("0x") ? hex.slice(2) : hex;
  const bytes = new Uint8Array(clean.length / 2);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = parseInt(clean.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function unixToDate(seconds: number | null | undefined): string {
  if (!seconds) return "—";
  return new Date(seconds * 1000).toISOString().slice(0, 10);
}

export function statusTone(status: number | null): string {
  if (status === 1) return "bg-emerald-50 text-emerald-800 border-emerald-200";
  if (status === 2) return "bg-red-50 text-red-800 border-red-200";
  return "bg-amber-50 text-amber-800 border-amber-200";
}
