import { render, screen, act, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import App from "../../src/renderer/App";
import { createDashboardFetchMock, stubWindowBackendApi } from "./testUtils";

describe("App", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
    vi.stubGlobal("fetch", createDashboardFetchMock());
    stubWindowBackendApi();
  });

  it("renders the sidebar with app title", async () => {
    render(<App />);
    expect(await screen.findByText("Clinical Registry")).toBeInTheDocument();
  });

  it("renders the search bar", async () => {
    render(<App />);
    expect(await screen.findByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("renders the dashboard as default page", async () => {
    render(<App />);
    expect(await screen.findByText(/No progress yet/i)).toBeInTheDocument();
  });

  it("renders the theme toggle", async () => {
    render(<App />);
    expect(await screen.findByText(/^Dark Mode$/i)).toBeInTheDocument();
  });

  it("holds page fetches until the backend reports ready after a slow start", async () => {
    let listener: ((status: { state: "starting" | "ready" | "error" | "stopped"; message: string | null }) => void) | null = null;
    const fetchMock = createDashboardFetchMock();
    vi.stubGlobal("fetch", fetchMock);

    window.api = {
      backend: {
        getStatus: vi.fn().mockResolvedValue({ state: "starting", message: "Launching backend" }),
        waitForReady: vi.fn().mockResolvedValue({ state: "ready", message: null }),
        restart: vi.fn().mockResolvedValue({ state: "ready", message: null }),
        onStatusChange: vi.fn().mockImplementation((callback) => {
          listener = callback;
          return () => {
            listener = null;
          };
        }),
      },
    };

    render(<App />);

    expect(await screen.findByText("Preparing clinical data services")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/quiz/mastery"),
      expect.anything()
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/quiz/streak"),
      expect.anything()
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/quiz/history"),
      expect.anything()
    );

    act(() => {
      listener?.({ state: "ready", message: null });
    });

    await screen.findByText(/No progress yet/i);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/quiz/mastery"),
        expect.anything()
      )
    );
  });
});
