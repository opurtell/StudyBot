import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter, type MemoryRouterProps } from "react-router-dom";
import { vi } from "vitest";
import { ThemeProvider } from "../../src/renderer/hooks/useTheme";
import { BackendStatusProvider } from "../../src/renderer/hooks/useBackendStatus";
import { ResourceCacheProvider } from "../../src/renderer/providers/ResourceCacheProvider";
import { SettingsProvider } from "../../src/renderer/providers/SettingsProvider";

export function stubWindowBackendApi() {
  window.api = {
    backend: {
      getStatus: vi.fn().mockResolvedValue({ state: "ready" as const, message: null }),
      waitForReady: vi.fn().mockResolvedValue({ state: "ready" as const, message: null }),
      restart: vi.fn().mockResolvedValue({ state: "ready" as const, message: null }),
      onStatusChange: vi.fn().mockReturnValue(() => {}),
    },
  };
}

export function createDashboardFetchMock() {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes("/quiz/mastery")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    }
    if (url.includes("/quiz/streak")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ streak: 0, accuracy: 0 }),
      });
    }
    if (url.includes("/quiz/history")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ status: "ok" }),
    });
  });
}

function AppProviderStack({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <BackendStatusProvider>
        <ResourceCacheProvider>
          <SettingsProvider>{children}</SettingsProvider>
        </ResourceCacheProvider>
      </BackendStatusProvider>
    </ThemeProvider>
  );
}

function BackendProviderStack({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <BackendStatusProvider>{children}</BackendStatusProvider>
    </ThemeProvider>
  );
}

type RenderWithAppProvidersOptions = Omit<RenderOptions, "wrapper"> & {
  initialEntries?: MemoryRouterProps["initialEntries"];
};

export function renderWithAppProviders(ui: ReactElement, options?: RenderWithAppProvidersOptions) {
  const { initialEntries = ["/"], ...renderOptions } = options ?? {};
  return render(
    <AppProviderStack>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </AppProviderStack>,
    renderOptions
  );
}

export function renderWithAppProvidersNoRouter(children: ReactNode, options?: Omit<RenderOptions, "wrapper">) {
  return render(<AppProviderStack>{children}</AppProviderStack>, options);
}

export function renderWithBackendProviders(children: ReactNode, options?: Omit<RenderOptions, "wrapper">) {
  return render(<BackendProviderStack>{children}</BackendProviderStack>, options);
}
