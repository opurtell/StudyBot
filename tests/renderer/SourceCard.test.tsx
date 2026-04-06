import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SourceCard from "../../src/renderer/components/SourceCard";

describe("SourceCard", () => {
  it("renders source name and status", () => {
    render(
      <SourceCard
        name="ACTAS CMGs"
        type="PRIMARY SOURCE / REGULATORY"
        id="SRC-0001"
        progress={100}
        statusText="LAST SYNCED: 2H AGO"
        detail="12 Guidelines"
      />
    );
    expect(screen.getByText("ACTAS CMGs")).toBeInTheDocument();
    expect(screen.getByText("LAST SYNCED: 2H AGO")).toBeInTheDocument();
  });

  it("renders source type label", () => {
    render(
      <SourceCard
        name="Test Source"
        type="FIELD NOTES / OCR"
        id="SRC-0002"
        progress={50}
        statusText="SYNCING"
        detail="10 Files"
      />
    );
    expect(screen.getByText("FIELD NOTES / OCR")).toBeInTheDocument();
  });
});
