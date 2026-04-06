import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import Button from "../../src/renderer/components/Button";

describe("Button", () => {
  it("renders children text", () => {
    render(<Button>Start Session</Button>);
    expect(screen.getByRole("button", { name: "Start Session" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it("applies primary variant styles by default", () => {
    render(<Button>Primary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-primary");
    expect(btn.className).toContain("text-on-primary");
  });

  it("applies secondary variant styles", () => {
    render(<Button variant="secondary">Secondary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-surface-container-high");
    expect(btn.className).toContain("text-on-surface");
  });

  it("applies tertiary variant styles", () => {
    render(<Button variant="tertiary">Tertiary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("text-primary");
    expect(btn.className).not.toContain("bg-primary");
  });

  it("is disabled when disabled prop is true", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});