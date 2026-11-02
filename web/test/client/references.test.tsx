import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { documentPath } from "../../src/client/components/Feedback";
import { anonymous, axeViolations, mockApi, renderAt } from "./helpers";

const ref = { id: "LITFL_atrial_flutter", kind: "ref", number: "LITFL", title: "Atrial Flutter", section: "ECGs", scope: "all", versionDate: "2026-11-02" };

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("general references", () => {
  it("links general-reference questions to the references pages", () => {
    expect(documentPath("LITFL_atrial_flutter")).toBe("/references/LITFL_atrial_flutter");
    expect(documentPath("OPENRN_HA_heart_failure")).toBe("/references/OPENRN_HA_heart_failure");
    expect(documentPath("MED_01_Adrenaline")).toBe("/medications/MED_01_Adrenaline");
  });

  it("shows a reference with its attribution and licence and no scope picker", async () => {
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/references/LITFL_atrial_flutter": {
        ...ref,
        view: "icp_pacer",
        markdown: "## ECG features\n\n- Saw-tooth flutter waves",
        checksum: "x",
        attribution: '"Atrial Flutter", LITFL ECG Library, licensed under CC BY-NC-SA 4.0.',
        licence: "CC BY-NC-SA 4.0",
        sourceUrl: "https://litfl.com/atrial-flutter-ecg-library/",
        corpusVersion: "v1",
      },
    });
    const { container } = renderAt("/references/LITFL_atrial_flutter");
    expect(await screen.findByRole("heading", { name: "Atrial Flutter", level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/LITFL ECG Library · ECGs/)).toBeInTheDocument();
    expect(screen.getByText(/the CMGs take precedence/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CC BY-NC-SA 4.0" })).toHaveAttribute("href", "https://creativecommons.org/licenses/by-nc-sa/4.0/");
    expect(screen.queryByRole("group", { name: /your qualification/i })).not.toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("lists every general source and its licence on the sources page", async () => {
    mockApi({ "GET /api/me": anonymous });
    const { container } = renderAt("/sources");
    expect(await screen.findByRole("heading", { name: "Sources and licences" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open RN" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "LITFL ECG Library" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CC BY 4.0" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "CC BY-NC-SA 4.0" })).toHaveLength(2);
    expect(await axeViolations(container)).toEqual([]);
  });
});
