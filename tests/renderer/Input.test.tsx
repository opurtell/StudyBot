import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import Input from "../../src/renderer/components/Input";

describe("Input", () => {
  it("renders with placeholder text", () => {
    render(<Input placeholder="Enter answer..." />);
    expect(screen.getByPlaceholderText("Enter answer...")).toBeInTheDocument();
  });

  it("renders with a label", () => {
    render(<Input label="Clinical Notes" />);
    expect(screen.getByLabelText("Clinical Notes")).toBeInTheDocument();
  });

  it("accepts typed input", async () => {
    render(<Input placeholder="Type here" />);
    const input = screen.getByPlaceholderText("Type here");
    await userEvent.type(input, "adrenaline 1mg");
    expect(input).toHaveValue("adrenaline 1mg");
  });

  it("calls onChange when value changes", async () => {
    const handleChange = vi.fn();
    render(<Input placeholder="Test" onChange={handleChange} />);
    await userEvent.type(screen.getByPlaceholderText("Test"), "a");
    expect(handleChange).toHaveBeenCalled();
  });

  it("is disabled when disabled prop is true", () => {
    render(<Input placeholder="Disabled" disabled />);
    expect(screen.getByPlaceholderText("Disabled")).toBeDisabled();
  });
});