export interface QuotaBucket {
  used: number;
  limit: number;
  remaining: number;
}

export type Me =
  | { signedIn: false; tier: "anonymous" }
  | {
      signedIn: true;
      tier: "free";
      email: string;
      quota: { period: string; generations: QuotaBucket; marking: QuotaBucket };
    };

export interface PublicConfig {
  turnstileSiteKey: string;
  environment: string;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set("content-type", "application/json");
  const res = await fetch(`/api${path}`, { ...init, headers, credentials: "same-origin" });
  const data = (await res.json().catch(() => null)) as (T & { error?: string; message?: string }) | null;
  if (!res.ok) {
    throw new ApiError(res.status, data?.error ?? "unknown", data?.message ?? "Something went wrong. Try again shortly.");
  }
  return data as T;
}

export const api = {
  config: () => request<PublicConfig>("/config"),
  me: () => request<Me>("/me"),
  requestMagicLink: (email: string, turnstileToken: string) =>
    request<{ ok: true }>("/auth/magic-link", { method: "POST", body: JSON.stringify({ email, turnstileToken }) }),
  verify: (token: string) => request<{ ok: true }>("/auth/verify", { method: "POST", body: JSON.stringify({ token }) }),
  signOut: () => request<{ ok: true }>("/auth/sign-out", { method: "POST", body: "{}" }),
  deleteAccount: () => request<{ ok: true }>("/me", { method: "DELETE" }),
};
