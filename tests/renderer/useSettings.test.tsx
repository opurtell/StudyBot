import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useSettings } from "../../src/renderer/hooks/useSettings";
import type { SettingsConfig, ModelRegistry } from "../../src/renderer/types/api";
import { ResourceCacheProvider } from "../../src/renderer/providers/ResourceCacheProvider";
import { SettingsProvider } from "../../src/renderer/providers/SettingsProvider";

function jsonResponse(body: unknown, init?: { status?: number }) {
  const status = init?.status ?? 200;
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body === undefined ? "" : JSON.stringify(body)),
    json: () => Promise.resolve(body),
  } as Response;
}

const config: SettingsConfig = {
  providers: {
    anthropic: {
      api_key: "anthropic-key",
      default_model: "claude-haiku-4-5-20251001",
    },
    google: {
      api_key: "google-key",
      default_model: "gemini-3-flash-preview",
    },
    zai: {
      api_key: "zai-key",
      default_model: "glm-4.7",
    },
    openai: {
      api_key: "openai-key",
      default_model: "gpt-5.4-nano",
    },
  },
  active_provider: "anthropic",
  quiz_model: "claude-haiku-4-5-20251001",
  clean_model: "claude-opus-4.6",
  vision_model: "claude-sonnet-4.6",
  base_qualification: "AP",
  endorsements: [],
};

const registry: ModelRegistry = {
  anthropic: {
    low: "claude-haiku-4-5-20251001",
    medium: "claude-sonnet-4.6",
    high: "claude-opus-4.6",
  },
  google: {
    low: "gemini-3.1-flash-lite-preview",
    medium: "gemini-3-flash-preview",
    high: "gemini-2.5-pro",
  },
  zai: {
    low: "glm-4.7-flash",
    medium: "glm-4.7",
    high: "glm-5",
  },
  openai: {
    low: "gpt-5.4-nano",
    medium: "gpt-5.4-mini",
    high: "gpt-5.4",
  },
};

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (init?.method === "PUT" && url.includes("/settings")) {
      return Promise.resolve(jsonResponse({ detail: "save failed" }, { status: 500 }));
    }
    if (url.includes("/settings/models")) {
      return Promise.resolve(jsonResponse(registry));
    }
    if (url.includes("/settings")) {
      return Promise.resolve(jsonResponse(config));
    }
    return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
  });
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
  return (
    <ResourceCacheProvider>
      <SettingsProvider>{children}</SettingsProvider>
    </ResourceCacheProvider>
  );
}

describe("useSettings", () => {
  it("loads settings and model registry", async () => {
    const { result } = renderHook(() => useSettings(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.config).toEqual(config);
    expect(result.current.modelRegistry).toEqual(registry);
    expect(result.current.error).toBeNull();
  });

  it("surfaces save failures through the shared error path", async () => {
    const { result } = renderHook(() => useSettings(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    let saveResult = false;
    await act(async () => {
      saveResult = await result.current.save(config);
    });

    expect(saveResult).toBe(false);
    expect(result.current.error).toBe("save failed");
    expect(result.current.saving).toBe(false);
  });

  it("keeps settings usable when model registry load fails", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/settings/models")) {
        return Promise.resolve(
          jsonResponse({ detail: "registry unavailable" }, { status: 500 })
        );
      }
      if (url.includes("/settings")) {
        return Promise.resolve(jsonResponse(config));
      }
      return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
    });

    const { result } = renderHook(() => useSettings(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.config).toEqual(config);
    expect(result.current.modelRegistry).toBeNull();
    expect(result.current.error).toBe("registry unavailable");
  });
});
