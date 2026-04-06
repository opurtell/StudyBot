import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "../../src/renderer/hooks/useTheme";
import Feedback from "../../src/renderer/pages/Feedback";
import type { FeedbackNavigationState } from "../../src/renderer/types/api";

const feedbackState: FeedbackNavigationState = {
  questionText: "Question text",
  userAnswer: "User answer",
  elapsedSeconds: 12,
  category: "Cardiac",
  questionType: "recall",
  evaluation: {
    score: "partial",
    correct_elements: ["correct point"],
    missing_or_wrong: ["missing point"],
    source_quote: "Source quote",
    source_citation: "CMG 1",
    feedback_summary: "Feedback summary",
    model_id: "test-model",
  },
  sessionId: "test-session-123",
  questionCount: 3,
};

function renderFeedback(initialEntries = [{ pathname: "/feedback", state: feedbackState }]) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/" element={<div>Archive Home</div>} />
          <Route path="/quiz" element={<div>Quiz Home</div>} />
          <Route path="/feedback" element={<Feedback />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );
}

describe("Feedback page shortcuts", () => {
  it("returns to quiz with ctrl+arrowright", async () => {
    const user = userEvent.setup();

    renderFeedback();
    await user.keyboard("{Control>}{ArrowRight}{/Control}");

    await waitFor(() => expect(screen.getByText("Quiz Home")).toBeInTheDocument());
  });

  it("continues quiz with ctrl+arrowright when session exists", async () => {
    const user = userEvent.setup();

    renderFeedback();
    await user.keyboard("{Control>}{ArrowRight}{/Control}");

    await waitFor(() => expect(screen.getByText("Quiz Home")).toBeInTheDocument());
  });

  it("returns to archive with escape", async () => {
    const user = userEvent.setup();

    renderFeedback();
    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.getByText("Archive Home")).toBeInTheDocument());
  });
});
