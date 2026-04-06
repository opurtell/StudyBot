import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FeedbackSplitView from "../../src/renderer/components/FeedbackSplitView";
import type { EvaluateResponse } from "../../src/renderer/types/api";

const evaluation: EvaluateResponse = {
  score: "partial",
  correct_elements: ["hypotension identified"],
  missing_or_wrong: ["tachycardia not mentioned"],
  source_quote: "Hypovolemic shock presents with hypotension and tachycardia.",
  source_citation: "CMG 14.1",
  feedback_summary: "Good identification of hypotension.",
  model_id: "test-model",
};

describe("FeedbackSplitView", () => {
  it("renders practitioner response section", () => {
    render(<FeedbackSplitView userAnswer="Low blood pressure" evaluation={evaluation} />);
    expect(screen.getByText("Your Answer")).toBeInTheDocument();
  });

  it("renders AI analysis section", () => {
    render(<FeedbackSplitView userAnswer="Low blood pressure" evaluation={evaluation} />);
    expect(screen.getByText("Evaluation")).toBeInTheDocument();
  });

  it("renders correct elements and missing items", () => {
    render(<FeedbackSplitView userAnswer="Low blood pressure" evaluation={evaluation} />);
    expect(screen.getByText("hypotension identified")).toBeInTheDocument();
    expect(screen.getByText("tachycardia not mentioned")).toBeInTheDocument();
  });
});
