import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RecentEntries from "../../src/renderer/components/RecentEntries";
import type { QuizAttempt } from "../../src/renderer/types/api";

const entries: QuizAttempt[] = [
  { id: 1, question_id: "q1", category: "Cardiac", question_type: "recall", score: "correct", elapsed_seconds: 12.5, source_citation: "CMG 14.1", created_at: "2026-04-03T10:00:00" },
  { id: 2, question_id: "q2", category: "Trauma", question_type: "scenario", score: "partial", elapsed_seconds: 45.0, source_citation: "CMG 8.2", created_at: "2026-04-03T09:30:00" },
];

describe("RecentEntries", () => {
  it("renders entry categories", () => {
    render(<RecentEntries entries={entries} />);
    expect(screen.getByText("Cardiac")).toBeInTheDocument();
    expect(screen.getByText("Trauma")).toBeInTheDocument();
  });

  it("renders score tags", () => {
    render(<RecentEntries entries={entries} />);
    expect(screen.getByText("correct")).toBeInTheDocument();
    expect(screen.getByText("partial")).toBeInTheDocument();
  });
});
