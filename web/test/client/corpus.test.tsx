import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { anonymous, axeViolations, mockApi, renderAt, signedIn } from "./helpers";

const summaries = [
  { id: "CMG_2_Cardiac_Arrest", kind: "cmg", number: "2", title: "Cardiac Arrest", section: "Cardiac", scope: "mixed", versionDate: null },
  { id: "CMG_3A_RSI", kind: "cmg", number: "3A", title: "Rapid Sequence Intubation", section: "Airway", scope: "icp", versionDate: null },
  { id: "CMG_CSM.A01_Manual_Clearance", kind: "csm", number: "CSM.A01", title: "Manual Clearance", section: "Clinical Skills", scope: "all", versionDate: null },
];

function detail(view: string, overrides: Record<string, unknown> = {}) {
  return {
    ...summaries[0],
    view,
    markdown: `# Cardiac Arrest\n\n#### Management\n\n- ${view} line\n\n<script>alert(1)</script>`,
    checksum: "x",
    attribution: "ACT Ambulance Service Clinical Management Guidelines",
    licence: "ACTAS public guidelines",
    sourceUrl: "https://cmg.ambulance.act.gov.au",
    corpusVersion: "v1",
    ...overrides,
  };
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("guidelines", () => {
  it("lists guidelines by section and switches to clinical skills", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/guidelines": { corpusVersion: "v1", items: summaries } });
    renderAt("/guidelines");
    expect(await screen.findByRole("heading", { name: "Cardiac" })).toBeInTheDocument();
    const rsi = screen.getByRole("link", { name: /rapid sequence intubation/i });
    expect(rsi).toHaveAttribute("href", "/guidelines/CMG_3A_RSI");
    expect(within(rsi).getByText("ICP only")).toBeInTheDocument();
    expect(within(screen.getByRole("link", { name: /cardiac arrest/i })).getByText("AP + ICP")).toBeInTheDocument();
    expect(screen.queryByText("Manual Clearance")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Clinical skills" }));
    expect(await screen.findByText("Manual Clearance")).toBeInTheDocument();
    expect(within(screen.getByRole("link", { name: /manual clearance/i })).getByText("AP")).toBeInTheDocument();
    expect(screen.queryByText("Cardiac Arrest")).not.toBeInTheDocument();
  });

  it("filters the list", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/guidelines": { corpusVersion: "v1", items: summaries } });
    renderAt("/guidelines");
    await userEvent.type(await screen.findByRole("searchbox", { name: /filter guidelines/i }), "rapid");
    expect(screen.queryByText("Cardiac Arrest")).not.toBeInTheDocument();
    expect(screen.getByText("Rapid Sequence Intubation")).toBeInTheDocument();
  });

  it("says when nothing is loaded", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/guidelines": { corpusVersion: null, items: [] } });
    renderAt("/guidelines");
    expect(await screen.findByText(/haven't been loaded yet/i)).toBeInTheDocument();
  });

  it("shows a guideline and refetches for the chosen scope, remembering it", async () => {
    const seen: string[] = [];
    const route = (view: string) => () => {
      seen.push(view);
      return { body: detail(view) };
    };
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/guidelines/CMG_2_Cardiac_Arrest?view=icp_pacer": route("icp_pacer"),
      "GET /api/guidelines/CMG_2_Cardiac_Arrest?view=ap": route("ap"),
      "GET /api/guidelines/CMG_2_Cardiac_Arrest?view=ap_pacer": route("ap_pacer"),
    });
    renderAt("/guidelines/CMG_2_Cardiac_Arrest");
    expect(await screen.findByRole("heading", { level: 1, name: "Cardiac Arrest" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Cardiac Arrest" })).toHaveLength(1);
    expect(screen.getByText("icp_pacer line")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    await userEvent.click(screen.getByRole("radio", { name: "AP" }));
    expect(await screen.findByText("ap line")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "PACER" }));
    expect(await screen.findByText("ap_pacer line")).toBeInTheDocument();
    expect(seen).toEqual(["icp_pacer", "ap", "ap_pacer"]);
    expect(JSON.parse(localStorage.getItem("scope-view") ?? "{}")).toEqual({ level: "ap", pacer: true });
    const article = screen.getByRole("article");
    expect(within(article).getByRole("link", { name: "cmg.ambulance.act.gov.au" })).toHaveAttribute("href", "https://cmg.ambulance.act.gov.au");
  });

  it("explains an ICP-only guideline in the AP view", async () => {
    localStorage.setItem("scope-view", JSON.stringify({ level: "ap", pacer: false }));
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/guidelines/CMG_3A_RSI?view=ap": detail("ap", { ...summaries[1], markdown: "" }),
    });
    renderAt("/guidelines/CMG_3A_RSI");
    expect(await screen.findByText(/ICP only, so it isn't in AP scope/i)).toBeInTheDocument();
  });

  it("shows a 404 from the API as an error", async () => {
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/guidelines/CMG_404?view=icp_pacer": { status: 404, body: { error: "not_found", message: "No such guideline." } },
    });
    renderAt("/guidelines/CMG_404");
    expect(await screen.findByRole("alert")).toHaveTextContent("No such guideline.");
  });

  it("has no detectable accessibility violations", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/guidelines/CMG_2_Cardiac_Arrest?view=icp_pacer": detail("icp_pacer") });
    const { container } = renderAt("/guidelines/CMG_2_Cardiac_Arrest");
    await screen.findByText("icp_pacer line");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("has an accessible list page", async () => {
    mockApi({ "GET /api/me": anonymous, "GET /api/guidelines": { corpusVersion: "v1", items: summaries } });
    const { container } = renderAt("/guidelines");
    await screen.findByRole("heading", { name: "Cardiac" });
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("markdown preparation", () => {
  it("drops the repeated title and closes gaps between heading levels", async () => {
    const { prepareMarkdown } = await import("../../src/client/components/DocumentView");
    expect(prepareMarkdown("# Asthma\n\n#### Adult\n\n- x\n\n###### Note\n\n- y", "Asthma")).toBe(
      "\n## Adult\n\n- x\n\n### Note\n\n- y",
    );
  });
});

describe("medications", () => {
  const med = { id: "MED_03_Adrenaline", kind: "med", number: "03", title: "Adrenaline", section: "Medicine", scope: "mixed", versionDate: null };

  it("lists monographs and opens one", async () => {
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/medications": { corpusVersion: "v1", items: [med] },
      "GET /api/medications/MED_03_Adrenaline?view=icp_pacer": detail("icp_pacer", { ...med, markdown: "# Adrenaline\n\n- 1mg IV" }),
    });
    renderAt("/medications");
    await userEvent.click(await screen.findByRole("link", { name: /adrenaline/i }));
    expect(await screen.findByRole("heading", { level: 1, name: "Adrenaline" })).toBeInTheDocument();
    expect(screen.getByText("1mg IV")).toBeInTheDocument();
    expect(screen.getByText(/ACTAS MED 03/)).toBeInTheDocument();
  });
});

describe("corpus admin", () => {
  const status = { version: "v1", builtAt: "2026-11-01", sourceCommit: "abc", documents: 194, chunks: 761, embedded: 0, pending: 761, retired: 0, vectorsAvailable: true };

  it("is hidden from non-admins", async () => {
    mockApi({ "GET /api/me": signedIn });
    renderAt("/account");
    await screen.findByRole("heading", { name: "Account" });
    expect(screen.queryByRole("heading", { name: /guideline corpus/i })).not.toBeInTheDocument();
  });

  it("syncs until nothing is pending", async () => {
    let pending = 761;
    mockApi({
      "GET /api/me": { ...signedIn, isAdmin: true },
      "GET /api/admin/corpus": () => ({ body: { ...status, pending, embedded: 761 - pending } }),
      "GET /api/admin/questions": { status: 500, body: { error: "x", message: "nope" } },
      "POST /api/admin/corpus/sync": () => {
        const embedded = Math.min(pending, 400);
        pending -= embedded;
        return { body: { available: true, embedded, removed: 0, pending } };
      },
    });
    renderAt("/account");
    await userEvent.click(await screen.findByRole("button", { name: /sync search index/i }));
    expect(await screen.findByText(/Done\. Embedded 761 chunks and removed 0\./)).toBeInTheDocument();
  });
});
