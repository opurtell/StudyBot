import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "../../src/renderer/hooks/useTheme";
import AppShell from "../../src/renderer/components/AppShell";
import { BackendStatusProvider } from "../../src/renderer/hooks/useBackendStatus";
import { ResourceCacheProvider } from "../../src/renderer/providers/ResourceCacheProvider";
import { stubWindowBackendApi } from "./testUtils";

beforeEach(() => {
  stubWindowBackendApi();
});

async function renderWithRouter(route = "/") {
  const rendered = render(
    <ThemeProvider>
      <BackendStatusProvider>
        <ResourceCacheProvider>
          <MemoryRouter initialEntries={[route]}>
            <AppShell>
              <div data-testid="child-content">Child Content</div>
            </AppShell>
          </MemoryRouter>
        </ResourceCacheProvider>
      </BackendStatusProvider>
    </ThemeProvider>
  );
  await screen.findByText("System Active");
  return rendered;
}

describe("AppShell", () => {
  it("renders the sidebar", async () => {
    await renderWithRouter();
    expect(screen.getByText("Study Assistant")).toBeInTheDocument();
  });

  it("renders the search bar", async () => {
    await renderWithRouter();
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("renders the dot-grid background", async () => {
    const { container } = await renderWithRouter();
    expect(container.querySelector(".dot-grid")).toBeInTheDocument();
  });

  it("renders children", async () => {
    await renderWithRouter();
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
  });

  it("renders the footer", async () => {
    await renderWithRouter();
    expect(screen.getByText("System Active")).toBeInTheDocument();
  });
});
