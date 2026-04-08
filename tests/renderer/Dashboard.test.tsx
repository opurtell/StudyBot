import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "../../src/renderer/hooks/useTheme";
import AppShell from "../../src/renderer/components/AppShell";
import Dashboard from "../../src/renderer/pages/Dashboard";
import { ResourceCacheProvider } from "../../src/renderer/providers/ResourceCacheProvider";
import { SettingsProvider } from "../../src/renderer/providers/SettingsProvider";
import { BackendStatusProvider } from "../../src/renderer/hooks/useBackendStatus";
import { BackgroundProcessProvider } from "../../src/renderer/providers/BackgroundProcessProvider";
import { stubWindowBackendApi } from "./testUtils";

beforeEach(() => {
  stubWindowBackendApi();
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/quiz/mastery")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve([
            { category: "Cardiac", total_attempts: 10, correct: 8, partial: 1, incorrect: 1, mastery_percent: 85, status: "strong" },
            { category: "Paediatrics", total_attempts: 5, correct: 1, partial: 0, incorrect: 4, mastery_percent: 20, status: "weak" },
          ]),
      });
    }
    if (url.includes("/quiz/streak")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ streak: 5, accuracy: 72 }) });
    }
    if (url.includes("/quiz/history")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }
    return Promise.resolve({ ok: false, status: 404 });
  });
});

function wrapDashboard(children: React.ReactNode, initialEntries?: string[]) {
  return (
    <ThemeProvider>
      <BackendStatusProvider>
        <BackgroundProcessProvider>
          <ResourceCacheProvider>
            <SettingsProvider>
              <MemoryRouter initialEntries={initialEntries}>
                {children}
              </MemoryRouter>
            </SettingsProvider>
          </ResourceCacheProvider>
        </BackgroundProcessProvider>
      </BackendStatusProvider>
    </ThemeProvider>
  );
}

describe("Dashboard", () => {
  it("renders knowledge heatmap with categories", async () => {
    render(
      wrapDashboard(
        <Routes>
          <Route path="/" element={<AppShell><Dashboard /></AppShell>} />
        </Routes>
      )
    );
    expect(await screen.findByText("Cardiac")).toBeInTheDocument();
  });

  it("renders Start Session button", async () => {
    render(
      wrapDashboard(
        <Routes>
          <Route path="/" element={<AppShell><Dashboard /></AppShell>} />
        </Routes>
      )
    );
    expect(await screen.findByText("Start Session")).toBeInTheDocument();
  });

  it("renders review suggestion with weakest category", async () => {
    render(
      wrapDashboard(
        <Routes>
          <Route path="/" element={<AppShell><Dashboard /></AppShell>} />
        </Routes>
      )
    );
    expect(await screen.findByText(/Review Paediatrics/)).toBeInTheDocument();
  });

  it("navigates to quiz when heatmap card is clicked", async () => {
    render(
      wrapDashboard(
        <Routes>
          <Route path="/" element={<AppShell><Dashboard /></AppShell>} />
          <Route path="/quiz" element={<div data-testid="quiz-page">Quiz</div>} />
        </Routes>,
        ["/"]
      )
    );
    const cardiac = await screen.findByText("Cardiac");
    fireEvent.click(cardiac);
    expect(await screen.findByTestId("quiz-page")).toBeInTheDocument();
  });

  it("navigates to quiz when review suggestion card is clicked", async () => {
    render(
      wrapDashboard(
        <Routes>
          <Route path="/" element={<AppShell><Dashboard /></AppShell>} />
          <Route path="/quiz" element={<div data-testid="quiz-page">Quiz</div>} />
        </Routes>,
        ["/"]
      )
    );
    const suggestion = await screen.findByText(/Review Paediatrics/);
    fireEvent.click(suggestion);
    expect(await screen.findByTestId("quiz-page")).toBeInTheDocument();
  });

  it("navigates to /quiz without section when category is unresolvable", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/quiz/mastery")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve([
              { category: "XyzUnknown", total_attempts: 3, correct: 0, partial: 0, incorrect: 3, mastery_percent: 0, status: "weak" },
            ]),
        });
      }
      if (url.includes("/quiz/streak")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ streak: 0, accuracy: 0 }) });
      }
      if (url.includes("/quiz/history")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      return Promise.resolve({ ok: false, status: 404 });
    });

    render(
      wrapDashboard(
        <Routes>
          <Route path="/" element={<AppShell><Dashboard /></AppShell>} />
          <Route path="/quiz" element={<div data-testid="quiz-page">Quiz</div>} />
        </Routes>,
        ["/"]
      )
    );
    const unknownCard = await screen.findByText("XyzUnknown");
    fireEvent.click(unknownCard);
    expect(await screen.findByTestId("quiz-page")).toBeInTheDocument();
  });
});
