import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen } from "@testing-library/react";
import { AppRoutes } from "../../src/renderer/App";
import { createDashboardFetchMock, renderWithAppProviders, stubWindowBackendApi } from "./testUtils";

describe("Focus mode routing", () => {
  beforeEach(() => {
    stubWindowBackendApi();
    vi.stubGlobal("fetch", createDashboardFetchMock());
  });

  function renderAppAt(route: string) {
    return renderWithAppProviders(<AppRoutes />, { initialEntries: [route] });
  }

  it("renders sidebar on dashboard route", async () => {
    renderAppAt("/");
    expect(await screen.findByText("Study Assistant")).toBeInTheDocument();
  });

  it("hides sidebar on quiz route", async () => {
    renderAppAt("/quiz");
    expect(await screen.findByText("Start Quiz")).toBeInTheDocument();
    expect(screen.queryByText("Study Assistant")).not.toBeInTheDocument();
  });

  it("hides sidebar on feedback route", async () => {
    renderAppAt("/feedback");
    expect(await screen.findByText("No evaluation data available")).toBeInTheDocument();
    expect(screen.queryByText("Study Assistant")).not.toBeInTheDocument();
  });
});
