import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "../../src/renderer/hooks/useTheme";
import AppShell from "../../src/renderer/components/AppShell";
import Settings from "../../src/renderer/pages/Settings";
import { ResourceCacheProvider } from "../../src/renderer/providers/ResourceCacheProvider";
import { SettingsProvider } from "../../src/renderer/providers/SettingsProvider";
import { BackendStatusProvider } from "../../src/renderer/hooks/useBackendStatus";
import { stubWindowBackendApi } from "./testUtils";

beforeEach(() => {
  stubWindowBackendApi();
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/quiz/blacklist")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }
    if (url.includes("/settings/models")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
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
          }),
      });
    }
    if (url.includes("/settings")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            providers: {
              anthropic: {
                api_key: "old-anthropic",
                default_model: "claude-haiku-4-5-20251001",
              },
              google: {
                api_key: "old-google",
                default_model: "gemini-3-flash-preview",
              },
              zai: {
                api_key: "old-zai",
                default_model: "glm-4.7-flash",
              },
            },
            active_provider: "anthropic",
            quiz_model: "claude-haiku-4-5-20251001",
            clean_model: "claude-opus-4.6",
            skill_level: "AP",
          }),
      });
    }
    return Promise.resolve({ ok: false, status: 404 });
  });
});

describe("Settings", () => {
  it("renders curator settings heading", async () => {
    render(
      <ThemeProvider>
        <BackendStatusProvider>
          <ResourceCacheProvider>
            <SettingsProvider>
              <MemoryRouter>
                <Routes>
                  <Route path="/" element={<AppShell><Settings /></AppShell>} />
                </Routes>
              </MemoryRouter>
            </SettingsProvider>
          </ResourceCacheProvider>
        </BackendStatusProvider>
      </ThemeProvider>
    );
    expect(await screen.findByRole("heading", { name: "Curator Settings" })).toBeInTheDocument();
  });

  it("saves updated API keys and selected models", async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <BackendStatusProvider>
          <ResourceCacheProvider>
            <SettingsProvider>
              <MemoryRouter>
                <Routes>
                  <Route path="/" element={<AppShell><Settings /></AppShell>} />
                </Routes>
              </MemoryRouter>
            </SettingsProvider>
          </ResourceCacheProvider>
        </BackendStatusProvider>
      </ThemeProvider>
    );

    await screen.findByRole("heading", { name: "Curator Settings" });

    const anthropicInput = screen.getByLabelText("Anthropic API Key");
    fireEvent.change(anthropicInput, { target: { value: "new-anthropic-key" } });

    await user.selectOptions(screen.getByLabelText("Quiz Agent Model"), "gemini-2.5-pro");
    await user.selectOptions(screen.getByLabelText("Cleaning Agent Model"), "glm-5");

    await user.click(screen.getByRole("button", { name: "Save Configuration" }));

    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    const saveCall = fetchMock.mock.calls.find(
      ([url, init]) => url.includes("/settings") && init && (init as RequestInit).method === "PUT"
    );

    expect(saveCall).toBeTruthy();
    expect(JSON.parse(String((saveCall?.[1] as RequestInit).body))).toMatchObject({
      providers: {
        anthropic: {
          api_key: "new-anthropic-key",
          default_model: "claude-haiku-4-5-20251001",
        },
        google: {
          api_key: "old-google",
          default_model: "gemini-2.5-pro",
        },
        zai: { api_key: "old-zai" },
      },
      quiz_model: "gemini-2.5-pro",
      clean_model: "glm-5",
    });
    expect(await screen.findByText("Settings Saved")).toBeInTheDocument();
  });
});
