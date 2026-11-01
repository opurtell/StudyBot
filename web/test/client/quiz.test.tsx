import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { anonymous, axeViolations, mockApi, renderAt, signedIn } from "./helpers";

const question = {
  id: "aaaaaaaaaaaaaaa1",
  text: "What BGL defines hypoglycaemia?",
  type: "recall",
  difficulty: "easy",
  category: "Medical",
  citation: "ACTAS CMG 10",
  documentId: "CMG_10_Diabetic",
  documentNumber: "10",
  documentTitle: "Diabetic Emergencies",
  origin: "bank",
};

const reveal = {
  questionId: question.id,
  sourceText: "[ACTAS CMG 10: Diabetic Emergencies]\nHypoglycaemia is a BGL below 4 mmol/L.",
  citation: "ACTAS CMG 10",
  documentId: "CMG_10_Diabetic",
  documentTitle: "Diabetic Emergencies",
  attribution: "ACT Ambulance Service Clinical Management Guidelines",
};

const lists = {
  "GET /api/guidelines": { corpusVersion: "v1", items: [] },
  "GET /api/medications": { corpusVersion: "v1", items: [] },
};

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

function body(init: RequestInit | undefined) {
  return JSON.parse(String(init?.body)) as Record<string, unknown>;
}

describe("quiz", () => {
  it("lets a guest answer, reveal the reference and report, remembering what they've seen", async () => {
    const sent: Record<string, unknown>[] = [];
    mockApi({
      "GET /api/me": anonymous,
      ...lists,
      "POST /api/quiz/next": (init: RequestInit | undefined) => {
        sent.push(body(init));
        return { body: { question, exhausted: false, canGenerate: false, quota: null } };
      },
      [`POST /api/quiz/questions/${question.id}/reveal`]: reveal,
      [`POST /api/quiz/questions/${question.id}/report`]: (init: RequestInit | undefined) => {
        expect(body(init)).toEqual({ reason: "incorrect", detail: "Wrong number" });
        return { body: { ok: true, withdrawn: false } };
      },
    });
    const { container } = renderAt("/quiz");
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    expect(await screen.findByRole("heading", { name: question.text })).toBeInTheDocument();
    expect(screen.getByText(/From the question library/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /mark my answer/i })).not.toBeInTheDocument();
    expect(sent[0]).toMatchObject({ view: "icp_pacer", exclude: [] });

    await userEvent.click(screen.getByRole("button", { name: "Reveal reference" }));
    expect(await screen.findByText(/BGL below 4 mmol\/L/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Read Diabetic Emergencies/ })).toHaveAttribute("href", "/guidelines/CMG_10_Diabetic");

    await userEvent.click(screen.getByRole("button", { name: /report a problem/i }));
    await userEvent.click(screen.getByRole("radio", { name: "Clinically wrong" }));
    await userEvent.type(screen.getByRole("textbox", { name: /details/i }), "Wrong number");
    await userEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText(/reported for review/)).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: "Next question" }));
    expect(sent[1]).toMatchObject({ exclude: [question.id] });
  });

  it("sends the chosen scope", async () => {
    const sent: Record<string, unknown>[] = [];
    mockApi({
      "GET /api/me": anonymous,
      ...lists,
      "POST /api/quiz/next": (init: RequestInit | undefined) => {
        sent.push(body(init));
        return { body: { question, exhausted: false, canGenerate: false, quota: null } };
      },
    });
    renderAt("/quiz");
    await userEvent.click(await screen.findByRole("radio", { name: "AP" }));
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await screen.findByRole("heading", { name: question.text });
    expect(sent[0]).toMatchObject({ view: "ap" });
  });

  it("marks a signed-in user's answer and shows the remaining allowance", async () => {
    mockApi({
      "GET /api/me": signedIn,
      ...lists,
      "POST /api/quiz/next": { question, exhausted: false, canGenerate: true, quota: signedIn.quota },
      [`POST /api/quiz/questions/${question.id}/mark`]: (init: RequestInit | undefined) => {
        expect(body(init)).toMatchObject({ view: "icp_pacer", answer: "Below 4" });
        return {
          body: {
            ...reveal,
            score: "partial",
            correctElements: ["Below 4"],
            missingOrWrong: ["Units: mmol/L"],
            sourceQuote: "BGL below 4 mmol/L",
            feedbackSummary: "Give the units.",
            quota: { ...signedIn.quota, marking: { used: 1, limit: 30, remaining: 29 } },
          },
        };
      },
    });
    renderAt("/quiz");
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    await userEvent.type(await screen.findByRole("textbox", { name: "Your answer" }), "Below 4");
    await userEvent.click(screen.getByRole("button", { name: "Mark my answer (30 left)" }));
    expect(await screen.findByText("Partly correct")).toBeInTheDocument();
    expect(screen.getByText("Units: mmol/L")).toBeInTheDocument();
    expect(screen.getByText("Give the units.")).toBeInTheDocument();
  });

  it("shows why an answer wasn't scored", async () => {
    mockApi({
      "GET /api/me": signedIn,
      ...lists,
      "POST /api/quiz/next": { question, exhausted: false, canGenerate: true, quota: signedIn.quota },
      [`POST /api/quiz/questions/${question.id}/mark`]: {
        status: 502,
        body: { error: "unreadable_response", message: "The marking model returned an unreadable response, so your answer was not scored. Please try again." },
      },
    });
    renderAt("/quiz");
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    await userEvent.type(await screen.findByRole("textbox", { name: "Your answer" }), "Below 4");
    await userEvent.click(screen.getByRole("button", { name: /mark my answer/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/not scored/);
    expect(screen.getByRole("textbox", { name: "Your answer" })).toHaveValue("Below 4");
  });

  it("offers a generated question when the library runs out", async () => {
    mockApi({
      "GET /api/me": signedIn,
      ...lists,
      "POST /api/quiz/next": { question: null, exhausted: true, canGenerate: true, quota: signedIn.quota },
      "POST /api/quiz/generate": {
        question: { ...question, origin: "live" },
        duplicate: false,
        quota: { ...signedIn.quota, generations: { used: 4, limit: 20, remaining: 16 } },
      },
    });
    renderAt("/quiz");
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    await userEvent.click(await screen.findByRole("button", { name: "Generate a new question (17 left this month)" }));
    expect(await screen.findByText(/Newly generated/)).toBeInTheDocument();
  });
});

describe("question admin", () => {
  it("lists reported questions and retires one", async () => {
    let retired = false;
    const reported = {
      id: question.id,
      text: question.text,
      status: "flagged",
      statusReason: "reported",
      citation: "ACTAS CMG 10",
      documentId: "CMG_10_Diabetic",
      sourceText: "source",
      origin: "bank",
      reports: [{ reason: "incorrect", detail: "Wrong dose", createdAt: 0 }],
    };
    mockApi({
      "GET /api/me": { ...signedIn, isAdmin: true },
      "GET /api/admin/corpus": { version: "v1", builtAt: null, sourceCommit: null, documents: 0, chunks: 0, embedded: 0, pending: 0, retired: 0, vectorsAvailable: false },
      "GET /api/admin/questions": () => ({
        body: {
          summary: { byStatus: { active: 10, flagged: retired ? 0 : 1 }, activeByView: { ap: 6, ap_pacer: 6, icp: 10, icp_pacer: 10 }, activeByDifficulty: {}, live: 0 },
          reported: retired ? [] : [reported],
          liveAi: true,
          today: { generations: 0, marks: 2, caps: { gen: 200, eval: 1000 } },
          month: { costUsd: 0.0123, calls: 2, unreadable: 0 },
        },
      }),
      [`POST /api/admin/questions/${question.id}/status`]: (init: RequestInit | undefined) => {
        expect(body(init)).toEqual({ status: "retired" });
        retired = true;
        return { body: { ok: true } };
      },
    });
    renderAt("/account");
    expect(await screen.findByText(/incorrect: Wrong dose/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retire" }));
    expect(await screen.findByText("Nothing reported.")).toBeInTheDocument();
  });
});
