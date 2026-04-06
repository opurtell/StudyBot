import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "../../src/renderer/hooks/useTheme";
import Sidebar from "../../src/renderer/components/Sidebar";

function renderSidebar() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    </ThemeProvider>
  );
}

describe("Sidebar", () => {
  it("renders the app title", () => {
    renderSidebar();
    expect(screen.getByText("Clinical Registry")).toBeInTheDocument();
  });

  it("renders the version label", () => {
    renderSidebar();
    expect(screen.getByText(/Archival Protocol/i)).toBeInTheDocument();
  });

  it("renders all primary navigation items", () => {
    renderSidebar();
    expect(screen.getByText("Observations")).toBeInTheDocument();
    expect(screen.getByText("Clinical Guidelines")).toBeInTheDocument();
    expect(screen.getByText("CMG & Notes Status")).toBeInTheDocument();
    expect(screen.getByText("Medications")).toBeInTheDocument();
  });

  it("renders the settings link", () => {
    renderSidebar();
    expect(screen.getByText("Curator Settings")).toBeInTheDocument();
  });

  it("renders the Start Session button", () => {
    renderSidebar();
    expect(
      screen.getByRole("button", { name: /start revision/i })
    ).toBeInTheDocument();
  });

  it("renders a theme toggle button", () => {
    renderSidebar();
    // The theme toggle shows "Dark Mode" in light theme
    expect(screen.getByText(/^Dark Mode$/i)).toBeInTheDocument();
  });
});
