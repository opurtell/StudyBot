import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import Card from "../../src/renderer/components/Card";

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const handleClick = vi.fn();
    render(<Card onClick={handleClick}>Clickable</Card>);
    await userEvent.click(screen.getByText("Clickable"));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it("has button role when onClick is provided", () => {
    render(<Card onClick={() => {}}>Interactive</Card>);
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("has no button role when static", () => {
    render(<Card>Static</Card>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("applies hover class when interactive", () => {
    render(<Card onClick={() => {}}>Interactive</Card>);
    const card = screen.getByRole("button");
    expect(card.className).toContain("hover:bg-surface-container-lowest");
  });

  it("is keyboard accessible when interactive", async () => {
    const handleClick = vi.fn();
    render(<Card onClick={handleClick}>Interactive</Card>);
    const card = screen.getByRole("button");
    card.focus();
    await userEvent.keyboard("{Enter}");
    expect(handleClick).toHaveBeenCalled();
  });
});