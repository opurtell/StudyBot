import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useApi } from "../../src/renderer/hooks/useApi";
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

describe("useApi", () => {
  it("fetches data successfully", async () => {
    const mockData = { streak: 5, accuracy: 72.3 };
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(jsonResponse(mockData));

    const { result } = renderHook(
      () => useApi<{ streak: number; accuracy: number }>("/quiz/streak"),
      { wrapper }
    );

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBeNull();
  });

  it("handles mapped request errors", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse({ detail: "Server exploded" }, { status: 500 })
    );

    const { result } = renderHook(() => useApi<{ streak: number }>("/quiz/streak"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Server exploded");
    expect(result.current.data).toBeNull();
  });

  it("exposes manual refetch", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ streak: 1 }))
      .mockResolvedValueOnce(jsonResponse({ streak: 2 }));

    const { result } = renderHook(() => useApi<{ streak: number }>("/quiz/streak"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(() => result.current.refetch());
    await waitFor(() => expect(result.current.data).toEqual({ streak: 2 }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("ignores stale results from superseded requests", async () => {
    let firstResolve: ((value: Response) => void) | null = null;
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            firstResolve = resolve;
          })
      )
      .mockResolvedValueOnce(jsonResponse({ streak: 2 }));

    const { result } = renderHook(() => useApi<{ streak: number }>("/quiz/streak"), {
      wrapper,
    });

    await act(async () => {
      await result.current.refetch();
    });

    expect(firstResolve).not.toBeNull();
    firstResolve!(jsonResponse({ streak: 1 }));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ streak: 2 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("skips requests when no path is provided", async () => {
    const { result } = renderHook(() => useApi<{ streak: number }>(""), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
