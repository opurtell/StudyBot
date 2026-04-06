import { describe, it, expect } from "vitest";
import { resolveTopic } from "../../src/renderer/utils/resolveTopic";

describe("resolveTopic", () => {
  it("returns section for exact display name match", () => {
    expect(resolveTopic("Paediatrics")).toBe("Paediatric");
  });

  it("returns section for exact section value match", () => {
    expect(resolveTopic("Paediatric")).toBe("Paediatric");
  });

  it("is case-insensitive", () => {
    expect(resolveTopic("cardiac")).toBe("Cardiac");
    expect(resolveTopic("TRAUMA")).toBe("Trauma");
  });

  it("trims whitespace", () => {
    expect(resolveTopic("  Cardiac  ")).toBe("Cardiac");
  });

  it("returns section when input starts with a known section value", () => {
    expect(resolveTopic("Cardiac Arrest")).toBe("Cardiac");
  });

  it("returns section when a known section value starts with the input", () => {
    expect(resolveTopic("Toxico")).toBe("Toxicology");
  });

  it("returns null for unrecognised category", () => {
    expect(resolveTopic("Unknown Category")).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(resolveTopic("")).toBeNull();
  });

  it("maps Medications to Medicine section", () => {
    expect(resolveTopic("Medications")).toBe("Medicine");
  });

  it("maps Clinical Skills to Clinical Skill section", () => {
    expect(resolveTopic("Clinical Skills")).toBe("Clinical Skill");
  });
});
