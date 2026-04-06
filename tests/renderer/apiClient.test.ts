import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiGet } from "../../src/renderer/lib/apiClient";

function jsonResponse(body: unknown, init?: { status?: number }) {
  const status = init?.status ?? 200;
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body === undefined ? "" : JSON.stringify(body)),
    json: () => Promise.resolve(body),
  } as Response;
}

describe("apiClient", () => {
  beforeEach(() => {
    vi.useRealTimers();
    global.fetch = vi.fn();
    window.api = {
      backend: {
        getStatus: vi.fn().mockResolvedValue({ state: "ready", message: null }),
        waitForReady: vi.fn().mockResolvedValue({ state: "ready", message: null }),
        restart: vi.fn().mockResolvedValue({ state: "ready", message: null }),
        onStatusChange: vi.fn().mockReturnValue(() => {}),
      },
    };
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("waits for backend readiness and returns parsed data", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ streak: 5, accuracy: 80 })
    );

    const result = await apiGet<{ streak: number; accuracy: number }>("/quiz/streak");

    expect(window.api!.backend.waitForReady).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:7777/quiz/streak",
      expect.objectContaining({ method: "GET" })
    );
    expect(result).toEqual({ streak: 5, accuracy: 80 });
  });

  it("surfaces backend-starting without issuing a fetch", async () => {
    window.api!.backend.waitForReady = vi.fn().mockResolvedValue({
      state: "starting",
      message: "Backend is starting",
    });

    await expect(apiGet("/quiz/streak")).rejects.toMatchObject({
      category: "backend-starting",
      message: "Backend is starting",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("surfaces backend-unavailable without issuing a fetch", async () => {
    window.api!.backend.waitForReady = vi.fn().mockResolvedValue({
      state: "error",
      message: "Backend failed",
    });

    await expect(apiGet("/quiz/streak")).rejects.toMatchObject({
      category: "backend-unavailable",
      message: "Backend failed",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("maps 4xx responses to invalid-request", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ detail: "Bad input" }, { status: 400 })
    );

    await expect(apiGet("/settings")).rejects.toMatchObject({
      category: "invalid-request",
      message: "Bad input",
      status: 400,
    });
  });

  it("maps 5xx responses to server-error", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ detail: "Server exploded" }, { status: 500 })
    );

    await expect(apiGet("/settings")).rejects.toMatchObject({
      category: "server-error",
      message: "Server exploded",
      status: 500,
    });
  });

  it("retries startup failures when attempts remain", async () => {
    window.api!.backend.waitForReady = vi
      .fn()
      .mockResolvedValueOnce({ state: "starting", message: "Booting" })
      .mockResolvedValueOnce({ state: "ready", message: null });
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(jsonResponse({ ok: true }));

    const result = await apiGet<{ ok: boolean }>("/health", { retries: 2 });

    expect(window.api!.backend.waitForReady).toHaveBeenCalledTimes(2);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(result).toEqual({ ok: true });
  });

  it("does not retry 4xx responses", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ detail: "Bad input" }, { status: 400 })
    );

    await expect(apiGet("/settings", { retries: 3 })).rejects.toMatchObject({
      category: "invalid-request",
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("maps fetch failures to backend-unavailable and retries while attempts remain", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    const result = await apiGet<{ ok: boolean }>("/health", { retries: 2 });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result).toEqual({ ok: true });
  });

  it("maps timeout aborts to timeout errors", async () => {
    vi.useFakeTimers();
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (_url: string, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          const signal = init?.signal as AbortSignal;
          signal.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true }
          );
        })
    );

    const request = apiGet("/slow", { timeoutMs: 10 });
    const assertion = expect(request).rejects.toMatchObject({
      category: "timeout",
      message: "Request timed out",
    });

    await vi.advanceTimersByTimeAsync(10);
    await assertion;
  });

  it("retries timeout failures when attempts remain", async () => {
    vi.useFakeTimers();
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockImplementationOnce(
        (_url: string, init?: RequestInit) =>
          new Promise((_resolve, reject) => {
            const signal = init?.signal as AbortSignal;
            signal.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true }
            );
          })
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    const request = apiGet<{ ok: boolean }>("/slow", { timeoutMs: 10, retries: 2 });
    await vi.advanceTimersByTimeAsync(10);

    await expect(request).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
