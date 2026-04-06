import { recordRequestDiagnostic } from "./devDiagnostics";

const API_BASE = "http://127.0.0.1:7777";
const DEFAULT_TIMEOUT_MS = 15000;

export const LLM_REQUEST_TIMEOUT_MS = 120_000;

export type ApiErrorCategory =
  | "backend-starting"
  | "backend-unavailable"
  | "timeout"
  | "invalid-request"
  | "server-error";

export class ApiClientError extends Error {
  constructor(
    public readonly category: ApiErrorCategory,
    message: string,
    public readonly status?: number
  ) {
    super(message);
    Object.setPrototypeOf(this, ApiClientError.prototype);
  }
}

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  headers?: Record<string, string>;
  body?: unknown;
  retries?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
}

function normalizePath(path: string) {
  if (path.startsWith("/")) return path;
  return `/${path}`;
}

export function isApiClientError(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError;
}

export function getApiErrorMessage(error: unknown, fallback = "Unknown error") {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function buildHeaders(options: ApiRequestOptions) {
  const headers: Record<string, string> = { ...options.headers };
  if (options.body !== undefined && options.body !== null && typeof options.body !== "string") {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
  }
  return headers;
}

function bodyPayload(body: unknown) {
  if (body === undefined || body === null) return undefined;
  return typeof body === "string" ? body : JSON.stringify(body);
}

async function ensureBackendReady() {
  if (!window.api?.backend) return;
  const status = await window.api.backend.waitForReady();
  if (status.state === "ready") return;
  if (status.state === "starting") {
    throw new ApiClientError("backend-starting", status.message ?? "Backend is starting");
  }
  throw new ApiClientError(
    "backend-unavailable",
    status.message ?? "Local services are unavailable",
    undefined
  );
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  if ("text" in response && typeof response.text === "function") {
    const text = await response.text();
    if (!text) {
      return undefined as unknown as T;
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      return undefined as unknown as T;
    }
  }

  if ("json" in response && typeof response.json === "function") {
    return (await response.json()) as T;
  }

  return undefined as unknown as T;
}

async function parseErrorBody(response: Response) {
  if ("json" in response && typeof response.json === "function") {
    try {
      return await response.json();
    } catch {}
  }

  if ("text" in response && typeof response.text === "function") {
    try {
      const text = await response.text();
      if (!text) {
        return null;
      }
      return JSON.parse(text);
    } catch {}
  }

  return null;
}

async function createErrorFromResponse(response: Response) {
  let detail = `Request failed (${response.status})`;

  try {
    const parsed = await parseErrorBody(response);
    if (parsed && typeof parsed === "object") {
      if ("detail" in parsed && typeof parsed.detail === "string") {
        detail = parsed.detail;
      } else if ("message" in parsed && typeof parsed.message === "string") {
        detail = parsed.message;
      }
    }
  } catch {}

  const category = response.status >= 500 ? "server-error" : "invalid-request";
  return new ApiClientError(category, detail, response.status);
}

function shouldRetry(error: ApiClientError) {
  return (
    error.category === "backend-starting" ||
    error.category === "backend-unavailable" ||
    error.category === "timeout"
  );
}

function handleFetchError(error: unknown, abortedByTimeout: boolean) {
  if (isApiClientError(error)) {
    return error;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    if (abortedByTimeout) {
      return new ApiClientError("timeout", "Request timed out");
    }
    throw error;
  }
  const message = error instanceof Error ? error.message : "Network error";
  return new ApiClientError("backend-unavailable", message);
}

async function request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const normalizedPath = normalizePath(path);
  const method = options.method ?? "GET";
  const maxAttempts = Math.max(1, options.retries ?? 1);

  let lastError: ApiClientError | null = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const attemptStartedAt = Date.now();
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let removeSignalListener: (() => void) | undefined;
    let abortedByTimeout = false;
    let gateDurationMs = 0;
    const controller = new AbortController();

    if (options.signal) {
      const onAbort = () => controller.abort();
      options.signal.addEventListener("abort", onAbort, { once: true });
      removeSignalListener = () => options.signal?.removeEventListener("abort", onAbort);
      if (options.signal.aborted) {
        onAbort();
      }
    }

    try {
      const gateStartedAt = Date.now();
      await ensureBackendReady();
      gateDurationMs = Date.now() - gateStartedAt;

      timeoutId = setTimeout(() => {
        abortedByTimeout = true;
        controller.abort();
      }, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);

      const response = await fetch(`${API_BASE}${normalizedPath}`, {
        method,
        headers: buildHeaders(options),
        body: bodyPayload(options.body),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw await createErrorFromResponse(response);
      }

      const result = await parseResponse<T>(response);
      recordRequestDiagnostic({
        path: normalizedPath,
        method,
        attempt,
        durationMs: Date.now() - attemptStartedAt,
        gateDurationMs,
        status: "success",
        httpStatus: response.status,
        category: null,
        message: null,
        startedAt: new Date(attemptStartedAt).toISOString(),
        finishedAt: new Date().toISOString(),
      });
      return result;
    } catch (error) {
      let mapped: ApiClientError;
      try {
        mapped = handleFetchError(error, abortedByTimeout);
      } catch (abortError) {
        recordRequestDiagnostic({
          path: normalizedPath,
          method,
          attempt,
          durationMs: Date.now() - attemptStartedAt,
          gateDurationMs,
          status: "aborted",
          httpStatus: null,
          category: null,
          message: abortError instanceof Error ? abortError.message : "Request aborted",
          startedAt: new Date(attemptStartedAt).toISOString(),
          finishedAt: new Date().toISOString(),
        });
        throw abortError;
      }
      lastError = mapped;
      recordRequestDiagnostic({
        path: normalizedPath,
        method,
        attempt,
        durationMs: Date.now() - attemptStartedAt,
        gateDurationMs,
        status: "error",
        httpStatus: mapped.status ?? null,
        category: mapped.category,
        message: mapped.message,
        startedAt: new Date(attemptStartedAt).toISOString(),
        finishedAt: new Date().toISOString(),
      });
      if (attempt === maxAttempts || !shouldRetry(mapped)) {
        throw mapped;
      }
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      removeSignalListener?.();
    }
  }

  throw lastError ?? new ApiClientError("server-error", "Request failed");
}

export function apiGet<T>(path: string, options?: Omit<ApiRequestOptions, "method">) {
  return request<T>(path, { ...options, method: "GET" });
}

export function apiPost<T>(path: string, body?: unknown, options?: Omit<ApiRequestOptions, "method" | "body">) {
  return request<T>(path, { ...options, method: "POST", body });
}

export function apiPut<T>(path: string, body?: unknown, options?: Omit<ApiRequestOptions, "method" | "body">) {
  return request<T>(path, { ...options, method: "PUT", body });
}

export function apiDelete<T>(path: string, options?: Omit<ApiRequestOptions, "method">) {
  return request<T>(path, { ...options, method: "DELETE" });
}
