import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import AppShell from "../../src/renderer/components/AppShell";
import Library from "../../src/renderer/pages/Library";
import { renderWithAppProviders, stubWindowBackendApi } from "./testUtils";

beforeEach(() => {
  stubWindowBackendApi();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        sources: [
          {
            id: "SRC-0001",
            name: "ACTAS CMGs",
            type: "PRIMARY SOURCE / REGULATORY",
            filter_type: "primary",
            progress: 100,
            status_text: "INGESTED",
            detail: "56 Guidelines",
          },
          {
            id: "SRC-0004",
            name: "Notability Field Notes",
            type: "FIELD NOTES / OCR",
            filter_type: "field",
            progress: 97,
            status_text: "CLEANING IN PROGRESS",
            detail: "380 of 392 cleaned",
          },
        ],
        cleaning_feed: [
          {
            status: "active",
            label: "Notability OCR Cleaning",
            preview: "Clinical cleaning is part-complete for extracted Notability markdown.",
            detail: "380 of 392 cleaned",
          },
        ],
      }),
  } as Response);
});

describe("Library", () => {
  it("renders API-backed source data", async () => {
    renderWithAppProviders(
      <Routes>
        <Route path="/" element={<AppShell><Library /></AppShell>} />
      </Routes>,
      { initialEntries: ["/"] }
    );

    expect(await screen.findByText("ACTAS CMGs")).toBeInTheDocument();
    expect(screen.getByText("Notability OCR Cleaning")).toBeInTheDocument();
    expect(screen.getByText("56 Guidelines")).toBeInTheDocument();
  });

  it("filters repository cards using API data", async () => {
    renderWithAppProviders(
      <Routes>
        <Route path="/" element={<AppShell><Library /></AppShell>} />
      </Routes>,
      { initialEntries: ["/"] }
    );

    expect(await screen.findByText("ACTAS CMGs")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Field Notes / OCR" }));

    expect(screen.queryByText("ACTAS CMGs")).not.toBeInTheDocument();
    expect(screen.getByText("Notability Field Notes")).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Server Error",
    } as Response);

    renderWithAppProviders(
      <Routes>
        <Route path="/" element={<AppShell><Library /></AppShell>} />
      </Routes>,
      { initialEntries: ["/"] }
    );

    expect(await screen.findByText(/Failed to load source repository/)).toBeInTheDocument();
  });
});
