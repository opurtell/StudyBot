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
      quota: Quota;
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

export type Difficulty = "easy" | "medium" | "hard";
export type Score = "correct" | "partial" | "incorrect";
export type ReportReason = "incorrect" | "out_of_scope" | "unclear" | "not_in_source" | "other";

export interface Quota {
  period: string;
  generations: QuotaBucket;
  marking: QuotaBucket;
}

export interface QuizQuestion {
  id: string;
  text: string;
  type: string;
  difficulty: Difficulty;
  category: string;
  citation: string;
  documentId: string;
  documentNumber: string;
  documentTitle: string;
  origin: "bank" | "live";
}

export interface QuizFilters {
  view: CorpusView;
  documentId?: string | null;
  difficulty?: Difficulty | null;
}

export interface NextResult {
  question: QuizQuestion | null;
  exhausted: boolean;
  canGenerate: boolean;
  quota: Quota | null;
}

export interface Reveal {
  questionId: string;
  sourceText: string;
  citation: string;
  documentId: string;
  documentTitle: string;
  attribution: string;
}

export interface Mark extends Reveal {
  score: Score;
  correctElements: string[];
  missingOrWrong: string[];
  sourceQuote: string;
  feedbackSummary: string;
  quota: Quota;
}

export interface ReportedQuestion {
  id: string;
  text: string;
  status: string;
  statusReason: string | null;
  citation: string;
  documentId: string;
  sourceText: string;
  origin: string;
  reports: { reason: string; detail: string | null; createdAt: number }[];
}

export interface QuestionAdminStatus {
  summary: {
    byStatus: Record<string, number>;
    activeByView: Record<CorpusView, number>;
    activeByDifficulty: Record<string, number>;
    live: number;
  };
  reported: ReportedQuestion[];
  liveAi: boolean;
  today: { generations: number; marks: number; caps: { gen: number; eval: number } };
  month: { costUsd: number; calls: number; unreadable: number };
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
  nextQuestion: (filters: QuizFilters, exclude: string[], repeat = false) =>
    request<NextResult>("/quiz/next", { method: "POST", body: JSON.stringify({ ...filters, exclude, repeat }) }),
  generateQuestion: (filters: QuizFilters) =>
    request<{ question: QuizQuestion; duplicate: boolean; quota: Quota }>("/quiz/generate", {
      method: "POST",
      body: JSON.stringify(filters),
    }),
  reveal: (id: string, view: CorpusView) =>
    request<Reveal>(`/quiz/questions/${id}/reveal`, { method: "POST", body: JSON.stringify({ view }) }),
  mark: (id: string, view: CorpusView, answer: string, elapsedMs: number) =>
    request<Mark>(`/quiz/questions/${id}/mark`, { method: "POST", body: JSON.stringify({ view, answer, elapsedMs }) }),
  report: (id: string, reason: ReportReason, detail: string) =>
    request<{ ok: true; withdrawn: boolean }>(`/quiz/questions/${id}/report`, {
      method: "POST",
      body: JSON.stringify({ reason, detail }),
    }),
  questionAdmin: () => request<QuestionAdminStatus>("/admin/questions"),
  setLiveAi: (enabled: boolean) =>
    request<{ liveAi: boolean }>("/admin/questions/live-ai", { method: "POST", body: JSON.stringify({ enabled }) }),
  setQuestionStatus: (id: string, status: "active" | "retired") =>
    request<{ ok: true }>(`/admin/questions/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
};
