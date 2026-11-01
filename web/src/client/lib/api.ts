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
      isAdmin?: boolean;
      quota: { period: string; generations: QuotaBucket; marking: QuotaBucket };
    };

export type CorpusView = "ap" | "ap_pacer" | "icp" | "icp_pacer";
export type DocumentScope = "all" | "mixed" | "icp" | "pacer";

export interface DocumentSummary {
  id: string;
  kind: "cmg" | "csm" | "med";
  number: string;
  title: string;
  section: string;
  scope: DocumentScope;
  versionDate: string | null;
}

export interface DocumentDetail extends DocumentSummary {
  view: CorpusView;
  markdown: string;
  checksum: string;
  attribution: string;
  licence: string;
  sourceUrl: string;
  corpusVersion: string;
}

export interface DocumentList {
  corpusVersion: string | null;
  items: DocumentSummary[];
}

export interface CorpusStatus {
  version: string | null;
  builtAt: string | null;
  sourceCommit: string | null;
  documents: number;
  chunks: number;
  embedded: number;
  pending: number;
  retired: number;
  vectorsAvailable: boolean;
}

export interface SyncResult {
  available: boolean;
  embedded: number;
  removed: number;
  pending: number;
}

export interface PublicConfig {
  environment: string;
  devSignIn: boolean;
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
  devSignIn: () => request<{ ok: true }>("/auth/dev-sign-in", { method: "POST", body: "{}" }),
  signOut: () => request<{ ok: true }>("/auth/sign-out", { method: "POST", body: "{}" }),
  deleteAccount: () => request<{ ok: true }>("/me", { method: "DELETE" }),
  guidelines: () => request<DocumentList>("/guidelines"),
  guideline: (id: string, view: CorpusView) =>
    request<DocumentDetail>(`/guidelines/${encodeURIComponent(id)}?view=${view}`),
  medications: () => request<DocumentList>("/medications"),
  medication: (id: string, view: CorpusView) =>
    request<DocumentDetail>(`/medications/${encodeURIComponent(id)}?view=${view}`),
  corpusStatus: () => request<CorpusStatus>("/admin/corpus"),
  syncCorpus: () => request<SyncResult>("/admin/corpus/sync", { method: "POST", body: "{}" }),
};
