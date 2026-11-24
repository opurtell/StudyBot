import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { anonymous, axeViolations, mockApi, renderAt, signedIn } from "./helpers";

const rubric = [
  { point: "Suspected ACS", critical: true, cites: [{ chunkId: "c1", documentId: "CMG_16_ACS", quote: "If in any doubt, treat as for ACS." }] },
  { point: "12 lead ECG", critical: false, cites: [{ chunkId: "c1", documentId: "CMG_16_ACS", quote: "12 lead ECG" }] },
];

const scenario = {
  id: "cccccccccccccc01",
  title: "Chest pain at home",
  dispatch: "58-year-old man, central chest pain, Belconnen.",
  category: "Cardiac",
  difficulty: "easy",
  patientGroup: "adult",
  documentId: "CMG_16_ACS",
  documentTitle: "Suspected ACS",
  stageCount: 2,
  stage: { ordinal: 1, reveal: "Pale, HR 96, BP 142/88.", question: "What is your working diagnosis?", focus: "assessment" },
};

const options = { options: [{ category: "Cardiac", difficulty: "easy", patientGroup: "adult", count: 3 }] };

function body(init: RequestInit | undefined) {
  return JSON.parse(String(init?.body)) as Record<string, unknown>;
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("Scenarios page", () => {
  it("runs a scenario stage by stage and scores the ticks", async () => {
    const attempts: Record<string, unknown>[] = [];
    mockApi({
      "GET /api/me": { ...signedIn, isAdmin: true },
      "GET /api/scenarios/options": options,
      "POST /api/scenarios/next": { scenario, exhausted: false },
      [`POST /api/scenarios/${scenario.id}/stages/1/reveal`]: {
        ordinal: 1,
        rubric,
        next: { ordinal: 2, reveal: "12 lead shows ST elevation.", question: "What now?", focus: "treatment" },
      },
      [`POST /api/scenarios/${scenario.id}/stages/2/reveal`]: { ordinal: 2, rubric, next: null },
      [`POST /api/scenarios/${scenario.id}/attempts`]: (init: RequestInit | undefined) => {
        attempts.push(body(init));
        return { body: { attemptId: "a1", score: "partial" } };
      },
    });
    const user = userEvent.setup();
    const { container } = renderAt("/scenarios");
    expect(await screen.findByRole("link", { name: "Scenarios" })).toBeInTheDocument();
    await user.click(await screen.findByRole("radio", { name: "Cardiac (3)" }));
    await user.click(screen.getByRole("button", { name: "Start scenario" }));
    expect(await screen.findByText(scenario.dispatch)).toBeInTheDocument();
    expect(screen.queryByText("Suspected ACS")).not.toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: /stage 1/i }), "ACS");
    await user.click(screen.getByRole("button", { name: "Reveal" }));
    await user.click(await screen.findByRole("checkbox", { name: /Suspected ACS/ }));
    expect(screen.getByText("If in any doubt, treat as for ACS.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next stage" }));

    expect(await screen.findByText("What now?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reveal" }));
    await user.click(await screen.findByRole("button", { name: "Finish" }));

    const debrief = await screen.findByRole("region", { name: "Debrief" });
    expect(debrief).toHaveTextContent("Overall");
    expect(debrief).toHaveTextContent("Partly correct");
    await waitFor(() => expect(attempts).toHaveLength(1));
    expect(attempts[0]).toMatchObject({ view: "icp_pacer", stages: [{ ordinal: 1, ticked: [0], answer: "ACS" }, { ordinal: 2, ticked: [] }] });
    expect(await axeViolations(container)).toEqual([]);
  });

  it("hides the nav link from non-admins and explains when scenarios are off", async () => {
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/scenarios/options": { status: 404, body: { error: "not_found", message: "Not found." } },
    });
    renderAt("/scenarios");
    expect(await screen.findByRole("alert")).toHaveTextContent("Scenarios aren't available yet.");
    expect(screen.queryByRole("link", { name: "Scenarios" })).not.toBeInTheDocument();
  });

  it("remembers a guest's seen scenarios and offers a repeat when they run out", async () => {
    let calls = 0;
    mockApi({
      "GET /api/me": anonymous,
      "GET /api/scenarios/options": options,
      "POST /api/scenarios/next": (init: RequestInit | undefined) => {
        calls += 1;
        const sent = body(init);
        if (calls === 1) return { body: { scenario, exhausted: false } };
        expect(sent.exclude).toEqual([scenario.id]);
        return { body: { scenario: null, exhausted: true, canRepeat: false } };
      },
    });
    const user = userEvent.setup();
    renderAt("/scenarios");
    await user.click(await screen.findByRole("button", { name: "Start scenario" }));
    expect(await screen.findByText(scenario.dispatch)).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("scenario-seen") ?? "[]")).toEqual([scenario.id]);
    renderAt("/scenarios");
    const starts = await screen.findAllByRole("button", { name: "Start scenario" });
    await user.click(starts[starts.length - 1]!);
    expect(await screen.findByRole("button", { name: "Repeat one" })).toBeInTheDocument();
  });
});
