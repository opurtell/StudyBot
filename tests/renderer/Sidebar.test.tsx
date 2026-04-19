import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "../../src/renderer/hooks/useTheme";
import { BackgroundProcessProvider } from "../../src/renderer/providers/BackgroundProcessProvider";
import { ServiceContext, type ServiceContextType } from "../../src/renderer/providers/ServiceProvider";
import Sidebar from "../../src/renderer/components/Sidebar";
import type { Service } from "../../src/renderer/types/api";

const mockService: Service = {
  id: "actas",
  display_name: "ACT Ambulance Service",
  region: "Australian Capital Territory",
  accent_colour: "#2D5A54",
  source_url: "https://cmg.ambulance.act.gov.au",
  qualifications: {
    bases: [{ id: "AP", display: "Ambulance Paramedic", implies: [] }],
    endorsements: [],
  },
};

const mockServiceContext: ServiceContextType = {
  services: [mockService],
  activeService: mockService,
  baseQualification: "Ambulance Paramedic",
  endorsements: [],
  setActiveService: async () => {},
  loading: false,
  error: null,
};

function renderSidebar() {
  return render(
    <ThemeProvider>
      <ServiceContext.Provider value={mockServiceContext}>
        <BackgroundProcessProvider>
          <MemoryRouter>
            <Sidebar />
          </MemoryRouter>
        </BackgroundProcessProvider>
      </ServiceContext.Provider>
    </ThemeProvider>
  );
}

describe("Sidebar", () => {
  it("renders the app title", () => {
    renderSidebar();
    expect(screen.getByText("Study Assistant")).toBeInTheDocument();
  });

  it("renders the version label", () => {
    renderSidebar();
    expect(screen.getByText(/Clinical Recall/i)).toBeInTheDocument();
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
    expect(screen.getByText("Settings")).toBeInTheDocument();
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
