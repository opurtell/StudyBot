import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DevelopmentDiagnostics from "../../src/renderer/components/DevelopmentDiagnostics";
import { renderWithAppProvidersNoRouter, stubWindowBackendApi } from "./testUtils";

vi.mock("../../src/renderer/lib/devDiagnostics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/renderer/lib/devDiagnostics")>();
  return {
    ...actual,
    isDevDiagnosticsEnabled: () => true,
    useDevDiagnostics: () => ({
      requests: [
        {
          id: 1,
          path: "/health",
          method: "GET",
          attempt: 1,
          startedAt: "2026-04-05T00:00:00.000Z",
          finishedAt: "2026-04-05T00:00:01.000Z",
          durationMs: 1000,
          gateDurationMs: 50,
          status: "success",
          httpStatus: 200,
          category: "ok",
          message: null,
        },
      ],
      cacheEvents: [],
    }),
  };
});

beforeEach(() => {
  stubWindowBackendApi();
});

describe("DevelopmentDiagnostics", () => {
  it("renders a scrollable panel", async () => {
    renderWithAppProvidersNoRouter(<DevelopmentDiagnostics />);

    fireEvent.click(screen.getByTestId("dev-diagnostics-toggle"));

    expect(await screen.findByTestId("dev-diagnostics-panel")).toHaveClass(
      "max-h-[calc(100vh-6rem)]",
      "overflow-hidden"
    );
    expect(screen.getByTestId("dev-diagnostics-scroll")).toHaveClass("overflow-y-auto");
  });

  it("closes from the panel close button", async () => {
    renderWithAppProvidersNoRouter(<DevelopmentDiagnostics />);

    fireEvent.click(screen.getByTestId("dev-diagnostics-toggle"));
    fireEvent.click(await screen.findByTestId("dev-diagnostics-close"));

    expect(screen.queryByTestId("dev-diagnostics-panel")).not.toBeInTheDocument();
  });
});
