import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import QuizQuestion from "../../src/renderer/components/QuizQuestion";

describe("QuizQuestion", () => {
  it("renders question badge and text", () => {
    render(
      <QuizQuestion
        questionNumber={14}
        text="Define the clinical presentation of hypovolemic shock."
        category="Cardiac"
      />
    );
    expect(screen.getByText("Question 14")).toBeInTheDocument();
    expect(screen.getByText("Define the clinical presentation of hypovolemic shock.")).toBeInTheDocument();
  });
});
