import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useApi } from "../../src/renderer/hooks/useApi";
import { ResourceCacheProvider } from "../../src/renderer/providers/ResourceCacheProvider";

function wrapper({ children }: PropsWithChildren) {
  return <ResourceCacheProvider>{children}</ResourceCacheProvider>;
}

describe("ResourceCacheProvider persistence", () => {
  beforeEach(() => {
    window.localStorage.clear();
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

  it("hydrates safe persisted cache entries on first render", async () => {
    window.localStorage.setItem(
      "studybot.resource-cache.v2",
      JSON.stringify({
        "/guidelines::3": {
          data: [
            {
              id: "cmg-1",
              cmg_number: "1",
              title: "General Care",
              section: "General Care",
              source_type: "cmg",
              is_icp_only: false,
            },
          ],
          updatedAt: 1234,
        },
      })
    );

    const { result } = renderHook(
      () =>
        useApi<
          Array<{
            id: string;
            cmg_number: string;
            title: string;
            section: string;
            source_type: string;
            is_icp_only: boolean;
          }>
        >("/guidelines"),
      { wrapper }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual([
      {
        id: "cmg-1",
        cmg_number: "1",
        title: "General Care",
        section: "General Care",
        source_type: "cmg",
        is_icp_only: false,
      },
    ]);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
