import type { ReactElement } from "react";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SearchBar from "../../src/renderer/components/SearchBar";
import { renderWithBackendProviders, stubWindowBackendApi } from "./testUtils";

function jsonResponse(body: unknown, init?: { status?: number }) {
  const status = init?.status ?? 200;
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body === undefined ? "" : JSON.stringify(body)),
    json: () => Promise.resolve(body),
  } as Response;
}

async function renderSearchBar(ui: ReactElement) {
  await act(async () => {
    renderWithBackendProviders(ui);
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useRealTimers();
  global.fetch = vi.fn();
  stubWindowBackendApi();
});

describe("SearchBar", () => {
  it("renders with search placeholder", async () => {
    await renderSearchBar(<SearchBar />);
    expect(await screen.findByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("renders with custom placeholder", async () => {
    await renderSearchBar(<SearchBar placeholder="Search guidelines..." />);
    expect(await screen.findByPlaceholderText("Search guidelines...")).toBeInTheDocument();
  });

  it("displays a search icon", async () => {
    await renderSearchBar(<SearchBar />);
    expect(await screen.findByText("search")).toBeInTheDocument();
  });

  it("loads search results through the shared client", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse([
        {
          content: "Manage airway with suction and adjuncts",
          source_type: "cmg",
          cmg_number: "2.1",
          category: "Airway",
        },
      ])
    );

    await renderSearchBar(<SearchBar />);

    await waitFor(() => {
      expect(screen.queryByText("Search is unavailable while the backend is offline.")).not.toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Search the archive"), {
      target: { value: "air" },
    });

    await waitFor(
      () =>
        expect(
          screen.getByText("Manage airway with suction and adjuncts")
        ).toBeInTheDocument(),
      { timeout: 2000 }
    );
    expect(global.fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:7777/search?q=air",
      expect.objectContaining({ method: "GET" })
    );
  });
});
