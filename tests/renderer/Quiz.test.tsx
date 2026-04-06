import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import Quiz from "../../src/renderer/pages/Quiz";
import Feedback from "../../src/renderer/pages/Feedback";
import { renderWithAppProviders, stubWindowBackendApi } from "./testUtils";

interface RenderOptions {
  initialEntries?: string[];
}

function renderQuizFlow({ initialEntries = ["/quiz"] }: RenderOptions = {}) {
  return renderWithAppProviders(
    <Routes>
      <Route path="/" element={<div>Archive Home</div>} />
      <Route path="/quiz" element={<Quiz />} />
      <Route path="/feedback" element={<Feedback />} />
    </Routes>,
    { initialEntries }
  );
}

function createFetchMock() {
  let questionCallCount = 0;

  return vi.fn().mockImplementation((url: string) => {
    if (url.includes("/session/start")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ session_id: "s1", mode: "random", blacklist: [] }),
      });
    }

    if (url.includes("/question/generate")) {
      questionCallCount += 1;
      const questionId = `q${questionCallCount}`;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          question_id: questionId,
          question_text: `Question ${questionCallCount}`,
          question_type: "recall",
          category: "Cardiac",
          difficulty: "medium",
          source_citation: `CMG ${questionCallCount}`,
        }),
      });
    }

    if (url.includes("/question/evaluate")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          score: "partial",
          correct_elements: ["correct point"],
          missing_or_wrong: ["missing point"],
          source_quote: "Source quote",
          source_citation: "CMG 1",
          feedback_summary: "Feedback summary",
        }),
      });
    }

    return Promise.resolve({ ok: false, status: 404 });
  });
}

beforeEach(() => {
  stubWindowBackendApi();
  global.fetch = createFetchMock();
});

describe("Quiz page", () => {
  it("renders session setup initially", async () => {
    renderQuizFlow();
    expect(await screen.findByText("Start Quiz")).toBeInTheDocument();
    expect(screen.getByText("Random")).toBeInTheDocument();
    expect(screen.getByText("Gap-Driven")).toBeInTheDocument();
  });

  it("starts a random session with the 1 shortcut", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");

    await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());
    expect(screen.getAllByText("Question 1").length).toBeGreaterThanOrEqual(1);
  });

  it("toggles variety mode with the v shortcut", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    expect(screen.getByRole("button", { name: /strict relevance/i })).toHaveClass("bg-surface-container-high");
    await user.keyboard("v");
    expect(screen.getByRole("button", { name: /strict relevance/i })).toHaveClass("bg-primary");
  });

  it("submits with enter in the textarea and preserves newline with shift+enter", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());

    const textarea = screen.getByPlaceholderText("Enter your clinical observations here...");
    await user.type(textarea, "line one");
    await user.keyboard("{Shift>}{Enter}{/Shift}line two");
    expect(textarea).toHaveValue("line one\nline two");

    await user.keyboard("{Enter}");

    await waitFor(() => expect(screen.getByText("View Full Analysis")).toBeInTheDocument());
  });

  it("submits with ctrl+enter from outside the textarea", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() => expect(screen.getByText("Skip")).toBeInTheDocument());

    const skipButton = screen.getByRole("button", { name: /skip/i });
    skipButton.focus();

    await user.keyboard("{Control>}{Enter}{/Control}");

    await waitFor(() => expect(screen.getByText("View Full Analysis")).toBeInTheDocument());
  });

  it("does not fire single-key shortcuts while typing in the textarea", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());

    const textarea = screen.getByPlaceholderText("Enter your clinical observations here...");
    await user.click(textarea);
    await user.keyboard("v");

    expect(textarea).toHaveValue("v");
  });

  it("reveals the reference with ctrl+shift+r", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() => expect(screen.getByText("Reveal Reference")).toBeInTheDocument());

    await user.keyboard("{Control>}{Shift>}R{/Shift}{/Control}");

    await waitFor(() => expect(screen.getByText("From the Source")).toBeInTheDocument());
  });

  it("ignores escape while the initial question is still loading", async () => {
    const user = userEvent.setup();
    let resolveQuestion:
      | ((value: {
          ok: boolean;
          json: () => Promise<{
            question_id: string;
            question_text: string;
            question_type: string;
            category: string;
            difficulty: string;
            source_citation: string;
          }>;
        }) => void)
      | undefined;

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/session/start")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ session_id: "s1", mode: "random", blacklist: [] }),
        });
      }

      if (url.includes("/question/generate")) {
        return new Promise<{
          ok: boolean;
          json: () => Promise<{
            question_id: string;
            question_text: string;
            question_type: string;
            category: string;
            difficulty: string;
            source_citation: string;
          }>;
        }>((resolve) => {
          resolveQuestion = resolve;
        });
      }

      return Promise.resolve({ ok: false, status: 404 });
    });

    renderQuizFlow();

    await user.keyboard("1");
    expect(screen.queryByText("Archive Home")).not.toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByText("Archive Home")).not.toBeInTheDocument();

    if (resolveQuestion) {
      resolveQuestion({
        ok: true,
        json: () => Promise.resolve({
          question_id: "q1",
          question_text: "Question 1",
          question_type: "recall",
          category: "Cardiac",
          difficulty: "medium",
          source_citation: "CMG 1",
        }),
      });
    }

    await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());
  });

  it("opens full analysis with ctrl+shift+a from inline feedback", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("Enter your clinical observations here..."), "clinical answer");
    await user.click(screen.getByPlaceholderText("Enter your clinical observations here..."));
    await user.type(screen.getByPlaceholderText("Enter your clinical observations here..."), "answer{enter}");
    await waitFor(() => expect(screen.getByText("View Full Analysis")).toBeInTheDocument());

    await user.keyboard("{Control>}{Shift>}A{/Shift}{/Control}");

    await waitFor(() => expect(screen.getByText("Answer Feedback")).toBeInTheDocument());
  });

  it("advances to the next question with ctrl+arrowright from inline feedback", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());

    await user.click(screen.getByPlaceholderText("Enter your clinical observations here..."));
    await user.type(screen.getByPlaceholderText("Enter your clinical observations here..."), "answer{enter}");
    await waitFor(() => expect(screen.getByText("View Full Analysis")).toBeInTheDocument());

    await user.keyboard("{Control>}{ArrowRight}{/Control}");

    await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());
    expect(screen.getAllByText("Question 2").length).toBeGreaterThanOrEqual(1);
  });

  it("exits to the archive with escape from feedback", async () => {
    const user = userEvent.setup();

    renderQuizFlow();

    await user.keyboard("1");
    await waitFor(() => expect(screen.getByPlaceholderText("Enter your clinical observations here...")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText("Enter your clinical observations here..."), "answer{enter}");
    await waitFor(() => expect(screen.getByText("View Full Analysis")).toBeInTheDocument());

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.getByText("Archive Home")).toBeInTheDocument());
  });

  it("shows a rate limit message when question generation is throttled", async () => {
    const user = userEvent.setup();

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/session/start")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ session_id: "s1", mode: "random", blacklist: [] }),
        });
      }

      if (url.includes("/question/generate")) {
        return Promise.resolve({
          ok: false,
          status: 429,
          json: () =>
            Promise.resolve({
              detail: "Provider quota exhausted",
              category: "rate_limit",
            }),
        });
      }

      return Promise.resolve({ ok: false, status: 404 });
    });

    renderQuizFlow();

    await user.keyboard("1");

    await waitFor(() => expect(screen.getByText("LLM Rate Limit Reached")).toBeInTheDocument());
    expect(screen.getByText(/switch to a different provider in Settings/i)).toBeInTheDocument();
  });
});
