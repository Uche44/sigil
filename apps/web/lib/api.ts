export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  errors?: Record<string, string> | string[];

  constructor(
    status: number,
    message: string,
    errors?: Record<string, string> | string[]
  ) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  token?: string | null;
  form?: FormData;
};

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.token) headers.Authorization = `Bearer ${options.token}`;

  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? (body ? "POST" : "GET"),
    headers,
    body,
    cache: "no-store",
  });

  const text = await response.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!response.ok) {
    const payload = data as { detail?: string; error?: string; errors?: Record<string, string> | string[] } | null;
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : typeof payload?.error === "string"
          ? payload.error
          : `Request failed (${response.status})`;
    throw new ApiError(response.status, message, payload?.errors);
  }

  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.errors && !Array.isArray(error.errors)) {
      const parts = Object.entries(error.errors).map(([key, value]) => `${key}: ${value}`);
      if (parts.length) return parts.join(", ");
    }
    if (Array.isArray(error.errors) && error.errors.length) return error.errors.join(", ");
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}
