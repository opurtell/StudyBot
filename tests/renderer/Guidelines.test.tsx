import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import AppShell from "../../src/renderer/components/AppShell";
import Guidelines from "../../src/renderer/pages/Guidelines";
import { renderWithAppProviders, stubWindowBackendApi } from "./testUtils";

const mockGuidelines = [
  { id: "CMG_4_Cardiac_Arrest", cmg_number: "4", title: "Cardiac Arrest – Adult", section: "Cardiac", source_type: "cmg" },
  { id: "CMG_23_Stroke", cmg_number: "23", title: "Stroke", section: "Neurology", source_type: "cmg" },
  { id: "CMG_03_Adrenaline", cmg_number: "03", title: "Adrenaline", section: "Medicine", source_type: "med" },
];

const mockDetail = {
  id: "CMG_4_Cardiac_Arrest",
  cmg_number: "4",
  title: "Cardiac Arrest – Adult",
  section: "Cardiac",
  source_type: "cmg",
  content_markdown: "#### Assessment\n- Unresponsive patient\n- Absent vital signs",
  dose_lookup: null,
  flowchart: null,
};

beforeEach(() => {
  stubWindowBackendApi();
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/guidelines/") && !url.includes("type=")) {
      const id = url.split("/guidelines/")[1].split("?")[0];
      if (id === mockDetail.id) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockDetail) });
      }
      return Promise.resolve({ ok: false, status: 404 });
    }
    if (url.includes("/guidelines")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockGuidelines) });
    }
    return Promise.resolve({ ok: false, status: 404 });
  });
});

function renderGuidelines() {
  return renderWithAppProviders(
    <Routes>
      <Route path="/*" element={<AppShell><Guidelines /></AppShell>} />
    </Routes>,
    { initialEntries: ["/guidelines"] }
  );
}

describe("Guidelines page", () => {
  it("renders the page title", async () => {
    renderGuidelines();
    expect(
      await screen.findByRole("heading", { name: "Clinical Guidelines" })
    ).toBeInTheDocument();
  });

  it("renders guideline cards after loading", async () => {
    renderGuidelines();
    expect(await screen.findByText("Cardiac Arrest – Adult")).toBeInTheDocument();
    expect(screen.getByText("Stroke")).toBeInTheDocument();
    expect(screen.getByText("Adrenaline")).toBeInTheDocument();
  });

  it("renders type filter chips", async () => {
    renderGuidelines();
    await screen.findByText("Cardiac Arrest – Adult");
    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Medication" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clinical Skill" })).toBeInTheDocument();
  });

  it("filters by type when CMG chip is clicked", async () => {
    renderGuidelines();
    await screen.findByText("Cardiac Arrest – Adult");
    fireEvent.click(screen.getByRole("button", { name: "CMG" }));
    expect(screen.getByText("Cardiac Arrest – Adult")).toBeInTheDocument();
    expect(screen.getByText("Stroke")).toBeInTheDocument();
    expect(screen.queryByText("Adrenaline")).not.toBeInTheDocument();
  });

  it("opens side panel when a card is clicked", async () => {
    renderGuidelines();
    await screen.findByText("Cardiac Arrest – Adult");
    fireEvent.click(screen.getByText("Cardiac Arrest – Adult"));
    expect(await screen.findByText("Assessment")).toBeInTheDocument();
    expect(screen.getAllByText("Start Revision").length).toBeGreaterThanOrEqual(2);
  });
});
