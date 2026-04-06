import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useMastery } from "../../src/renderer/hooks/useMastery";
import { ResourceCacheProvider } from "../../src/renderer/providers/ResourceCacheProvider";

function jsonResponse(body: unknown, init?: { status?: number }) {
  const status = init?.status ?? 200;
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body === undefined ? "" : JSON.stringify(body)),
    json: () => Promise.resolve(body),
  } as Response;
}

beforeEach(() => {
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

function wrapper({ children }: PropsWithChildren) {
  return <ResourceCacheProvider>{children}</ResourceCacheProvider>;
}

describe("useMastery", () => {
  it("returns mastery categories and streak data", async () => {
    const categories = [
      { category: "Cardiac", total_attempts: 10, correct: 8, partial: 1, incorrect: 1, mastery_percent: 85, status: "strong" as const },
    ];
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/quiz/mastery")) {
        return Promise.resolve(jsonResponse(categories));
      }
      if (url.includes("/quiz/streak")) {
        return Promise.resolve(jsonResponse({ streak: 5, accuracy: 85 }));
      }
      return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
    });

    const { result } = renderHook(() => useMastery(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.categories).toHaveLength(1);
    expect(result.current.categories[0].category).toBe("Cardiac");
    expect(result.current.streak).toBe(5);
    expect(result.current.accuracy).toBe(85);
  });

  it("surfaces shared-client messages on failure", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ detail: "Mastery unavailable" }, { status: 500 })
    );

    const { result } = renderHook(() => useMastery(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Mastery unavailable");
  });
});
