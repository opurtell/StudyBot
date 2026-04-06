import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import KnowledgeHeatmap from "../../src/renderer/components/KnowledgeHeatmap";
import type { CategoryMastery } from "../../src/renderer/types/api";

const categories: CategoryMastery[] = [
  { category: "Cardiac", total_attempts: 10, correct: 8, partial: 1, incorrect: 1, mastery_percent: 85, status: "strong" },
  { category: "Trauma", total_attempts: 5, correct: 2, partial: 1, incorrect: 2, mastery_percent: 50, status: "developing" },
  { category: "Paediatrics", total_attempts: 3, correct: 0, partial: 0, incorrect: 3, mastery_percent: 0, status: "weak" },
];

describe("KnowledgeHeatmap", () => {
  it("renders category cards with correct names", () => {
    render(<KnowledgeHeatmap categories={categories} />);
    expect(screen.getByText("Cardiac")).toBeInTheDocument();
    expect(screen.getByText("Trauma")).toBeInTheDocument();
    expect(screen.getByText("Paediatrics")).toBeInTheDocument();
  });

  it("renders mastery percentages", () => {
    render(<KnowledgeHeatmap categories={categories} />);
    expect(screen.getByText("85% Mastery")).toBeInTheDocument();
    expect(screen.getByText("50% Mastery")).toBeInTheDocument();
    expect(screen.getByText("0% Mastery")).toBeInTheDocument();
  });

  it("renders progress bars for each category", () => {
    const { container } = render(<KnowledgeHeatmap categories={categories} />);
    const bars = container.querySelectorAll("[role='progressbar']");
    expect(bars).toHaveLength(3);
  });

  it("calls onCategoryClick when a category card is clicked", () => {
    const handleClick = vi.fn();
    render(<KnowledgeHeatmap categories={categories} onCategoryClick={handleClick} />);
    fireEvent.click(screen.getByText("Cardiac"));
    expect(handleClick).toHaveBeenCalledWith("Cardiac");
  });

  it("does not render interactive cards when onCategoryClick is not provided", () => {
    const { container } = render(<KnowledgeHeatmap categories={categories} />);
    expect(container.querySelector("[role='button']")).toBeNull();
  });
});
