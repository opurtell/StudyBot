import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ServiceChip } from "../../src/renderer/components/ServiceChip";
import { ServiceContext, type ServiceContextType } from "../../src/renderer/providers/ServiceProvider";
import type { Service } from "../../src/renderer/types/api";

const mockService: Service = {
  id: "actas",
  display_name: "ACT Ambulance Service",
  region: "Australian Capital Territory",
  accent_colour: "#2D5A54",
  source_url: "https://cmg.ambulance.act.gov.au",
  qualifications: {
    bases: [
      { id: "AP", display: "Ambulance Paramedic", implies: [] },
    ],
    endorsements: [],
  },
};

const mockContext: ServiceContextType = {
  services: [mockService],
  activeService: mockService,
  baseQualification: "Ambulance Paramedic",
  endorsements: [],
  setActiveService: async () => {},
  loading: false,
  error: null,
};

function renderWithProvider(
  chip: React.ReactElement,
  ctx: ServiceContextType = mockContext
) {
  return render(
    <ServiceContext.Provider value={ctx}>{chip}</ServiceContext.Provider>
  );
}

describe("ServiceChip", () => {
  it("renders the active service display name", () => {
    renderWithProvider(<ServiceChip />);
    expect(
      screen.getByText("ACT Ambulance Service")
    ).toBeInTheDocument();
  });

  it("renders the base qualification", () => {
    renderWithProvider(<ServiceChip />);
    expect(
      screen.getByText("Ambulance Paramedic")
    ).toBeInTheDocument();
  });

  it("returns null when no active service", () => {
    const { container } = renderWithProvider(<ServiceChip />, {
      ...mockContext,
      activeService: null,
      baseQualification: "",
    });
    expect(container.innerHTML).toBe("");
  });

  it("applies the accent colour as inline style", () => {
    renderWithProvider(<ServiceChip />);
    const nameEl = screen.getByText("ACT Ambulance Service");
    expect(nameEl.style.color).toBe("rgb(45, 90, 84)");
  });
});
