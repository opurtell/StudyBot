import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ServiceSetupModal } from "../../src/renderer/components/ServiceSetupModal";
import { ServiceContext, type ServiceContextType } from "../../src/renderer/providers/ServiceProvider";
import type { Service } from "../../src/renderer/types/api";

// Mock SettingsProvider context
const mockSave = vi.fn().mockResolvedValue(true);
vi.mock("../../src/renderer/providers/SettingsProvider", () => ({
  useSettingsContext: () => ({
    config: {
      providers: {},
      active_provider: "anthropic",
      quiz_model: "haiku",
      clean_model: "sonnet",
      skill_level: "paramedic",
    },
    save: mockSave,
  }),
}));

const mockService: Service = {
  id: "actas",
  display_name: "ACT Ambulance Service",
  region: "Australian Capital Territory",
  accent_colour: "#2D5A54",
  source_url: "https://cmg.ambulance.act.gov.au",
  qualifications: {
    bases: [
      { id: "AP", display: "Ambulance Paramedic", implies: [] },
      { id: "ICP", display: "Intensive Care Paramedic", implies: ["AP"] },
    ],
    endorsements: [
      { id: "CC", display: "Critical Care", requires_base: ["ICP"] },
      { id: "MICA", display: "MICA", requires_base: ["AP", "ICP"] },
    ],
  },
};

const mockService2: Service = {
  id: "nswas",
  display_name: "NSW Ambulance",
  region: "New South Wales",
  accent_colour: "#1a3a5c",
  source_url: "https://example.com",
  qualifications: {
    bases: [{ id: "P", display: "Paramedic", implies: [] }],
    endorsements: [],
  },
};

const mockSetService = vi.fn().mockResolvedValue(undefined);

function createMockContext(overrides: Partial<ServiceContextType> = {}): ServiceContextType {
  return {
    services: [mockService, mockService2],
    activeService: null,
    baseQualification: "",
    endorsements: [],
    setActiveService: mockSetService,
    loading: false,
    error: null,
    ...overrides,
  };
}

function renderWithProviders(
  ui: React.ReactElement,
  ctx: ServiceContextType = createMockContext()
) {
  return render(
    <ServiceContext.Provider value={ctx}>{ui}</ServiceContext.Provider>
  );
}

describe("ServiceSetupModal", () => {
  it("renders when open={true}", () => {
    renderWithProviders(<ServiceSetupModal open={true} />);
    expect(screen.getByText("Select Your Service")).toBeInTheDocument();
  });

  it("does not render when open={false}", () => {
    const { container } = renderWithProviders(<ServiceSetupModal open={false} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows service list from context", () => {
    renderWithProviders(<ServiceSetupModal open={true} />);
    expect(screen.getByText("ACT Ambulance Service")).toBeInTheDocument();
    expect(screen.getByText("NSW Ambulance")).toBeInTheDocument();
    expect(screen.getByText("Australian Capital Territory")).toBeInTheDocument();
    expect(screen.getByText("New South Wales")).toBeInTheDocument();
  });

  it("selecting a service reveals qualification bases", async () => {
    renderWithProviders(<ServiceSetupModal open={true} />);

    // Qualification bases should NOT be visible before selecting a service
    expect(screen.queryByText("Qualification Base")).not.toBeInTheDocument();

    // Click on a service
    await userEvent.click(screen.getByText("ACT Ambulance Service"));

    // Now qualification bases should be visible
    expect(screen.getByText("Qualification Base")).toBeInTheDocument();
    expect(screen.getByText("Ambulance Paramedic")).toBeInTheDocument();
    expect(screen.getByText("Intensive Care Paramedic")).toBeInTheDocument();
  });

  it("selecting a base reveals endorsements filtered by requires_base", async () => {
    renderWithProviders(<ServiceSetupModal open={true} />);

    // Select service
    await userEvent.click(screen.getByText("ACT Ambulance Service"));

    // Endorsements should not yet be visible
    expect(screen.queryByText("Endorsements")).not.toBeInTheDocument();

    // Select ICP base — should show Critical Care (requires ICP only) and MICA (requires AP or ICP)
    await userEvent.click(screen.getByText("Intensive Care Paramedic"));

    expect(screen.getByText("Endorsements")).toBeInTheDocument();
    expect(screen.getByText("Critical Care")).toBeInTheDocument();
    expect(screen.getByText("MICA")).toBeInTheDocument();

    // Now switch to AP base — should show MICA only (not Critical Care)
    await userEvent.click(screen.getByText("Ambulance Paramedic"));

    expect(screen.getByText("Endorsements")).toBeInTheDocument();
    expect(screen.queryByText("Critical Care")).not.toBeInTheDocument();
    expect(screen.getByText("MICA")).toBeInTheDocument();
  });

  it("save button is disabled until base is selected", async () => {
    renderWithProviders(<ServiceSetupModal open={true} />);

    const confirmBtn = screen.getByRole("button", { name: "Confirm" });
    expect(confirmBtn).toBeDisabled();

    // Select a service
    await userEvent.click(screen.getByText("ACT Ambulance Service"));
    expect(confirmBtn).toBeDisabled();

    // Select a base
    await userEvent.click(screen.getByText("Ambulance Paramedic"));
    expect(confirmBtn).toBeEnabled();
  });

  it("calls save on confirm with selected values", async () => {
    renderWithProviders(<ServiceSetupModal open={true} />);

    await userEvent.click(screen.getByText("ACT Ambulance Service"));
    await userEvent.click(screen.getByText("Intensive Care Paramedic"));
    await userEvent.click(screen.getByText("Critical Care"));

    const confirmBtn = screen.getByRole("button", { name: "Confirm" });
    await userEvent.click(confirmBtn);

    expect(mockSetService).toHaveBeenCalledWith("actas");
    expect(mockSave).toHaveBeenCalled();
  });

  it("shows cancel button when onClose is provided", () => {
    const onClose = vi.fn();
    renderWithProviders(<ServiceSetupModal open={true} onClose={onClose} />);

    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("does not show cancel button when onClose is undefined (blocking)", () => {
    renderWithProviders(<ServiceSetupModal open={true} />);

    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("calls onClose when cancel is clicked", async () => {
    const onClose = vi.fn();
    renderWithProviders(<ServiceSetupModal open={true} onClose={onClose} />);

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("shows loading spinner when services are loading", () => {
    const ctx = createMockContext({ loading: true });
    const { container } = renderWithProviders(<ServiceSetupModal open={true} />, ctx);

    expect(container.querySelector(".loading-spinner")).toBeInTheDocument();
    expect(screen.queryByText("ACT Ambulance Service")).not.toBeInTheDocument();
  });
});
