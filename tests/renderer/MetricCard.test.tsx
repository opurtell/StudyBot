import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MetricCard from "../../src/renderer/components/MetricCard";

describe("MetricCard", () => {
  it("renders value and label", () => {
    render(<MetricCard value="14 days" label="Current Streak" />);
    expect(screen.getByText("14 days")).toBeInTheDocument();
    expect(screen.getByText("Current Streak")).toBeInTheDocument();
  });
});
