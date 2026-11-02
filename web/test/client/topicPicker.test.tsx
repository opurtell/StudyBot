import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildGroups, EVERYTHING, resolveSelection, selectionFromLink, togglePool } from "../../src/client/lib/quizSelection";
import { anonymous, axeViolations, mockApi, renderAt } from "./helpers";

const topics = [
  {
    section: "Cardiac",
    questions: 9,
    documents: [
      { id: "CMG_16_ACS", kind: "cmg", number: "16", title: "Suspected ACS", questions: 4 },
      { id: "CMG_4_Arrest", kind: "cmg", number: "4", title: "Cardiac Arrest: Adult", questions: 5 },
    ],
  },
  {
    section: "HAZMAT",
    questions: 2,
    documents: [{ id: "CMG_34_HAZMAT", kind: "cmg", number: "34", title: "CBRN / HAZMAT Incident", questions: 2 }],
  },
  {
    section: "Medicine",
    questions: 7,
    documents: [
      { id: "MED_03_Adrenaline", kind: "med", number: "03", title: "Adrenaline", questions: 4 },
      { id: "MED_29_Salbutamol", kind: "med", number: "29", title: "Salbutamol (Ventolin)", questions: 3 },
    ],
  },
  {
    section: "Clinical Skill",
    questions: 3,
    documents: [
      { id: "CSM_A01", kind: "csm", number: "CSM.A01", title: "Manual Clearance", questions: 1 },
      { id: "CSM_PA02", kind: "csm", number: "CSM.PA02", title: "Pulse Oximetry", questions: 2 },
    ],
  },
] as const;

const allTopics = [
  ...topics,
  { section: "Airway Management", questions: 2, documents: [{ id: "CMG_3A_RSI", kind: "cmg", number: "3A", title: "RSI", questions: 2 }] },
];

const question = {
  id: "aaaaaaaaaaaaaaa1",
  text: "What is the adult adrenaline dose?",
  type: "recall",
  difficulty: "easy",
  category: "Medicine",
  citation: "ACTAS MED 03",
  documentId: "MED_03_Adrenaline",
  documentNumber: "03",
  documentTitle: "Adrenaline",
  origin: "bank",
};

const groups = buildGroups(topics as never);
const noPrefs = { excludedSections: [], excludedDocuments: [] };

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("topic selection", () => {
  it("groups guidelines by section, medications together and skills by CSM group", () => {
    expect(groups.map((g) => g.label)).toEqual(["Cardiac", "HAZMAT", "All medications", "Airway (A)", "Patient assessment (PA)"]);
    expect(groups[0]!.docs.map((d) => d.number)).toEqual(["4", "16"]);
  });

  it("narrows to one pool, then toggles, and never leaves no pool", () => {
    const meds = togglePool(EVERYTHING, "med");
    expect(meds.pools).toEqual(["med"]);
    expect(togglePool(meds, "cmg").pools).toEqual(["cmg", "med"]);
    expect(togglePool(meds, "med").pools).toEqual(EVERYTHING.pools);
  });

  it("keeps a pool with nothing ticked whole when narrowing to only these", () => {
    const r = resolveSelection({ pools: ["cmg", "med"], mode: "only", picked: ["CMG_16_ACS"] }, groups, { excludedSections: ["HAZMAT"], excludedDocuments: [] });
    expect(r.filters).toEqual({ kinds: ["cmg", "med"], documentIds: ["CMG_16_ACS", "MED_03_Adrenaline", "MED_29_Salbutamol"], excludeDocumentIds: [] });
    expect(r.useSettings).toBe(false);
    expect(r.questions).toBe(11);
  });

  it("lets a tick override a topic excluded in Settings", () => {
    const r = resolveSelection({ pools: ["cmg"], mode: "only", picked: ["CMG_34_HAZMAT"] }, groups, { excludedSections: ["HAZMAT"], excludedDocuments: [] });
    expect(r.filters.documentIds).toEqual(["CMG_34_HAZMAT"]);
  });

  it("leaves ticked topics out in everything-except mode and still applies Settings", () => {
    const r = resolveSelection({ pools: EVERYTHING.pools, mode: "except", picked: ["MED_03_Adrenaline"] }, groups, { excludedSections: ["HAZMAT"], excludedDocuments: [] });
    expect(r.filters).toEqual({ kinds: null, documentIds: null, excludeDocumentIds: ["MED_03_Adrenaline"] });
    expect(r.useSettings).toBe(true);
    expect(r.questions).toBe(9 + 3 + 3);
  });

  it("turns heatmap and history links into ticks", () => {
    expect(selectionFromLink(groups, { document: "MED_29_Salbutamol", section: null })).toEqual({ pools: ["med"], mode: "only", picked: ["MED_29_Salbutamol"] });
    expect(selectionFromLink(groups, { document: null, section: "Cardiac" })).toEqual({ pools: ["cmg"], mode: "only", picked: ["CMG_4_Arrest", "CMG_16_ACS"] });
    expect(resolveSelection(EVERYTHING, groups, noPrefs).filters).toEqual({ kinds: null, documentIds: null, excludeDocumentIds: [] });
  });
});

describe("quiz topic picker", () => {
  function setup() {
    const sent: Record<string, unknown>[] = [];
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/topics?view=icp_pacer": { view: "icp_pacer", topics: allTopics },
      "GET /api/topics?view=ap": { view: "ap", topics },
      "POST /api/quiz/next": (init: RequestInit | undefined) => {
        sent.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
        return { body: { question, exhausted: false, canGenerate: false, quota: null } };
      },
    });
    return sent;
  }

  it("picks pools and topics, then sends them with the question request", async () => {
    const sent = setup();
    const { container } = renderAt("/quiz");
    await userEvent.click(await screen.findByRole("button", { name: /^Medications/ }));
    await userEvent.click(screen.getByRole("button", { name: /^Guidelines/ }));
    await userEvent.click(await screen.findByRole("button", { name: /Cardiac/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Suspected ACS/ }));
    const session = screen.getByRole("complementary", { name: "Your session" });
    expect(within(session).getByText("Guidelines + Medications")).toBeInTheDocument();
    expect(within(session).getByText(/11 questions in play · 1 picked/)).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await screen.findByRole("heading", { name: question.text });
    expect(sent[0]).toMatchObject({ kinds: ["cmg", "med"], documentIds: ["CMG_16_ACS", "MED_03_Adrenaline", "MED_29_Salbutamol"], excludeDocumentIds: [] });

    await userEvent.click(screen.getByRole("button", { name: "Next question" }));
    expect(sent[1]).toMatchObject({ documentIds: ["CMG_16_ACS", "MED_03_Adrenaline", "MED_29_Salbutamol"] });
    await userEvent.click(screen.getByRole("button", { name: "Change topics" }));
    expect(screen.getByRole("checkbox", { name: /Suspected ACS/ })).toBeChecked();
  });

  it("leaves out a whole section in everything-except mode", async () => {
    const sent = setup();
    renderAt("/quiz");
    await userEvent.click(await screen.findByRole("radio", { name: "AP" }));
    await userEvent.click(screen.getByRole("button", { name: "Everything except these" }));
    await userEvent.click(await screen.findByRole("checkbox", { name: "Leave out all of Cardiac" }));
    await userEvent.click(screen.getByRole("button", { name: /Skills/ }));
    await userEvent.click(screen.getByRole("button", { name: /^Everything All/ }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Search topics" }), "salb");
    expect(screen.getByRole("checkbox", { name: /Salbutamol/ })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /Adrenaline/ })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await screen.findByRole("heading", { name: question.text });
    expect(sent[0]).toMatchObject({ view: "ap", kinds: null, documentIds: null, excludeDocumentIds: ["CMG_4_Arrest", "CMG_16_ACS"] });
  });
});
