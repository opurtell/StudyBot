import { screen, within } from "@testing-library/react";
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
  section: "Medical",
  origin: "bank",
};

const reveal = {
  questionId: question.id,
  score: null,
  section: "Medical",
  sourceText: "Hypoglycaemia is a BGL below 4 mmol/L.",
  citation: "ACTAS CMG 10",
  documentId: "CMG_10_Diabetic",
  documentTitle: "Diabetic Emergencies",
  attribution: "ACT Ambulance Service Clinical Management Guidelines",
};

const topics = {
  view: "icp_pacer",
  topics: [
    { section: "Medical", questions: 40, documents: [{ id: "CMG_10_Diabetic", kind: "cmg", number: "10", title: "Diabetic Emergencies", questions: 40 }] },
    { section: "Trauma", questions: 30, documents: [{ id: "CMG_20_Burns", kind: "cmg", number: "20", title: "Burns", questions: 30 }] },
  ],
};

const lists = {
  "GET /api/guidelines": { corpusVersion: "v1", items: [] },
  "GET /api/medications": { corpusVersion: "v1", items: [] },
};

function guestAttempt(score: string | null, at = Date.now()) {
  return {
    id: `g-${at}-${score}`,
    questionId: question.id,
    questionText: question.text,
    documentId: question.documentId,
    documentTitle: question.documentTitle,
    section: "Medical",
    score,
    at,
  };
}

function body(init: RequestInit | undefined) {
  return JSON.parse(String(init?.body)) as Record<string, unknown>;
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("dashboard", () => {
  it("builds a guest's heatmap from progress kept in the browser", async () => {
    localStorage.setItem("guest-progress", JSON.stringify([guestAttempt("partial")]));
    mockApi({ "GET /api/me": anonymous, "GET /api/topics?view=icp_pacer": topics });
    const { container } = renderAt("/");
    const map = await screen.findByRole("list", { name: "Knowledge heatmap" });
    const tiles = within(map).getAllByRole("link");
    expect(tiles[0]).toHaveTextContent(/Medical.*50% · Developing.*1 answered of 40/);
    expect(tiles[0]).toHaveAttribute("href", "/quiz?section=Medical");
    expect(tiles[1]).toHaveTextContent(/Trauma.*Not started/);
    expect(screen.getByText(/saved in this browser only/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Practise this" })).toHaveAttribute("href", "/quiz?document=CMG_10_Diabetic");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("offers to add guest progress to the account after sign-in", async () => {
    localStorage.setItem("guest-progress", JSON.stringify([guestAttempt("correct", 1000), guestAttempt(null, 2000)]));
    const imported: unknown[] = [];
    mockApi({
      "GET /api/me": signedIn,
      "GET /api/progress": {
        sections: [],
        totals: { answered: 0, accuracy: null, streakDays: 0, studiedToday: false },
        weakest: null,
        recent: [],
      },
      "POST /api/progress/import": (init: RequestInit | undefined) => {
        imported.push(body(init).attempts);
        return { body: { imported: 2, skipped: 0 } };
      },
    });
    renderAt("/");
    await userEvent.click(await screen.findByRole("button", { name: "Add to my account" }));
    expect(await screen.findByText("Added 2 answers to your account.")).toBeInTheDocument();
    expect(imported).toEqual([
      [
        { questionId: question.id, score: "correct", at: 1000 },
        { questionId: question.id, score: null, at: 2000 },
      ],
    ]);
    expect(localStorage.getItem("guest-progress")).toBeNull();
  });

  it("shows a signed-in user's progress from the server", async () => {
    mockApi({
      "GET /api/me": signedIn,
      "GET /api/progress": {
        sections: [
          { section: "Cardiac", questions: 50, documents: [], answered: 4, correct: 4, partial: 0, incorrect: 0, percent: 100, status: "strong" },
        ],
        totals: { answered: 4, accuracy: 100, streakDays: 3, studiedToday: true },
        weakest: null,
        recent: [{ id: "att-1", questionId: question.id, questionText: question.text, documentId: question.documentId, documentTitle: question.documentTitle, section: "Medical", kind: "marked", score: "correct", at: Date.now() }],
      },
    });
    renderAt("/");
    expect(await screen.findByText("3 days")).toBeInTheDocument();
    expect(screen.getByText(/100% · Strong/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: new RegExp(question.text) })).toHaveAttribute("href", "/history/att-1");
  });
});

describe("self-marking", () => {
  it("records a guest's self-marked answer in the browser", async () => {
    mockApi({
      "GET /api/me": anonymous,
      ...lists,
      "POST /api/quiz/next": { question, exhausted: false, canGenerate: false, quota: null },
      [`POST /api/quiz/questions/${question.id}/reveal`]: (init: RequestInit | undefined) => {
        expect(body(init)).toMatchObject({ answer: "Under 4" });
        return { body: { ...reveal, attemptId: null } };
      },
    });
    renderAt("/quiz");
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    await userEvent.type(await screen.findByRole("textbox", { name: "Your answer" }), "Under 4");
    await userEvent.click(screen.getByRole("button", { name: "Reveal reference" }));
    expect(await screen.findByText("Under 4")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Partly" }));
    expect(await screen.findByText("Saved to your progress.")).toBeInTheDocument();
    const stored = JSON.parse(localStorage.getItem("guest-progress") ?? "[]") as { score: string; section: string }[];
    expect(stored).toEqual([expect.objectContaining({ score: "partial", section: "Medical" })]);
  });

  it("saves a signed-in user's self-mark to the account", async () => {
    const graded: unknown[] = [];
    mockApi({
      "GET /api/me": signedIn,
      ...lists,
      "POST /api/quiz/next": { question, exhausted: false, canGenerate: true, quota: signedIn.quota },
      [`POST /api/quiz/questions/${question.id}/reveal`]: { ...reveal, attemptId: "att-9" },
      "POST /api/quiz/attempts/att-9/self-grade": (init: RequestInit | undefined) => {
        graded.push(body(init));
        return { body: { ok: true, score: "correct" } };
      },
    });
    renderAt("/quiz");
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    await userEvent.click(await screen.findByRole("button", { name: "Reveal reference" }));
    await userEvent.click(await screen.findByRole("button", { name: "Got it" }));
    expect(await screen.findByText("Saved to your progress.")).toBeInTheDocument();
    expect(graded).toEqual([{ score: "correct" }]);
    expect(localStorage.getItem("guest-progress")).toBeNull();
  });

  it("starts a topic quiz from a heatmap link", async () => {
    const sent: Record<string, unknown>[] = [];
    mockApi({
      "GET /api/me": anonymous,
      ...lists,
      "POST /api/quiz/next": (init: RequestInit | undefined) => {
        sent.push(body(init));
        return { body: { question, exhausted: false, canGenerate: false, quota: null } };
      },
    });
    renderAt("/quiz?section=Medical");
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    await screen.findByRole("heading", { name: question.text });
    expect(sent[0]).toMatchObject({ section: "Medical", documentId: null });
  });
});

describe("settings sync", () => {
  it("saves a signed-in user's qualification and exclusions and uses them in quizzes", async () => {
    const saved: Record<string, unknown>[] = [];
    const sent: Record<string, unknown>[] = [];
    mockApi({
      "GET /api/me": { ...signedIn, settings: { qualification: "icp", pacer: false, excludedSections: [], excludedDocuments: [], saved: true } },
      "GET /api/topics?view=icp_pacer": topics,
      ...lists,
      "PUT /api/me/settings": (init: RequestInit | undefined) => {
        saved.push(body(init));
        return { body: { settings: { ...body(init), saved: true } } };
      },
      "POST /api/quiz/next": (init: RequestInit | undefined) => {
        sent.push(body(init));
        return { body: { question, exhausted: false, canGenerate: true, quota: signedIn.quota } };
      },
    });
    renderAt("/settings");
    expect(await screen.findByRole("radio", { name: "ICP" })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("radio", { name: "AP" }));
    await userEvent.click(await screen.findByRole("checkbox", { name: "Exclude Trauma" }));
    expect(saved.at(-1)).toEqual({ qualification: "ap", pacer: false, excludedSections: ["Trauma"], excludedDocuments: [] });

    await userEvent.click(screen.getAllByRole("link", { name: "Quiz" })[0]!);
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    await screen.findByRole("heading", { name: question.text });
    expect(sent[0]).toMatchObject({ view: "ap", excludedSections: ["Trauma"] });
  });

  it("carries a guest's settings over to a new account", async () => {
    localStorage.setItem("scope-view", JSON.stringify({ level: "ap", pacer: true }));
    const saved: Record<string, unknown>[] = [];
    mockApi({
      "GET /api/me": { ...signedIn, settings: { qualification: null, pacer: false, excludedSections: [], excludedDocuments: [], saved: false } },
      "GET /api/progress": { sections: [], totals: { answered: 0, accuracy: null, streakDays: 0, studiedToday: false }, weakest: null, recent: [] },
      "PUT /api/me/settings": (init: RequestInit | undefined) => {
        saved.push(body(init));
        return { body: { settings: body(init) } };
      },
    });
    renderAt("/");
    await screen.findByRole("heading", { name: /signed in as/i });
    await vi.waitFor(() => expect(saved).toEqual([{ qualification: "ap", pacer: true, excludedSections: [], excludedDocuments: [] }]));
  });
});

describe("history", () => {
  it("lists answers and opens the feedback view", async () => {
    mockApi({
      "GET /api/me": signedIn,
      "GET /api/progress/history": {
        items: [{ id: "att-1", questionId: question.id, questionText: question.text, documentId: question.documentId, documentTitle: question.documentTitle, section: "Medical", kind: "marked", score: "partial", at: Date.now() }],
        more: false,
      },
      "GET /api/progress/attempts/att-1": {
        id: "att-1",
        kind: "marked",
        score: "partial",
        answer: "Below 4",
        elapsedMs: 12000,
        at: Date.now(),
        evaluation: { correctElements: ["Below 4"], missingOrWrong: ["Units: mmol/L"], sourceQuote: "BGL below 4 mmol/L", feedbackSummary: "Give the units." },
        question: { id: question.id, text: question.text, difficulty: "easy", withdrawn: false },
        sourceText: reveal.sourceText,
        citation: "ACTAS CMG 10",
        documentId: question.documentId,
        documentTitle: question.documentTitle,
        section: "Medical",
        attribution: reveal.attribution,
      },
    });
    const { container } = renderAt("/history");
    await userEvent.click(await screen.findByRole("link", { name: new RegExp(question.text) }));
    expect(await screen.findByRole("heading", { level: 1, name: question.text })).toBeInTheDocument();
    expect(screen.getByText("Below 4", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("Units: mmol/L")).toBeInTheDocument();
    expect(screen.getByText("Partly correct")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Read Diabetic Emergencies/ })).toHaveAttribute("href", "/guidelines/CMG_10_Diabetic");
    expect(await axeViolations(container)).toEqual([]);
  });
});
