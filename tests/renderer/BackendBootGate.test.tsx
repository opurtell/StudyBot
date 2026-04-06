import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import BackendBootGate from "../../src/renderer/components/BackendBootGate";
import { BackendStatusProvider, useBackendStatus } from "../../src/renderer/hooks/useBackendStatus";

function renderWithProvider(children: ReactNode) {
  return render(<BackendStatusProvider>{children}</BackendStatusProvider>);
}

function StatusProbe() {
  const status = useBackendStatus();
  return <div data-testid="backend-state">{status.state}</div>;
}

describe("BackendBootGate", () => {
  it("blocks children while the backend is starting", async () => {
    window.api = {
      backend: {
        getStatus: vi.fn().mockResolvedValue({ state: "starting", message: "Launching backend" }),
        waitForReady: vi.fn().mockResolvedValue({ state: "ready", message: null }),
        restart: vi.fn().mockResolvedValue({ state: "ready", message: null }),
        onStatusChange: vi.fn().mockReturnValue(() => {}),
      },
    };

    renderWithProvider(
      <BackendBootGate>
        <div>Ready content</div>
      </BackendBootGate>
    );

    expect(await screen.findByText("Preparing clinical data services")).toBeInTheDocument();
    expect(screen.queryByText("Ready content")).not.toBeInTheDocument();
  });

  it("restarts the backend from the error gate and then renders children", async () => {
    const restart = vi.fn().mockResolvedValue({ state: "ready", message: null });

    window.api = {
      backend: {
        getStatus: vi.fn().mockResolvedValue({ state: "error", message: "Backend failed" }),
        waitForReady: vi.fn().mockResolvedValue({ state: "ready", message: null }),
        restart,
        onStatusChange: vi.fn().mockReturnValue(() => {}),
      },
    };

    renderWithProvider(
      <BackendBootGate>
        <div>Ready content</div>
      </BackendBootGate>
    );

    expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(restart).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText("Ready content")).toBeInTheDocument());
  });

  it("updates renderer state when backend status events arrive", async () => {
    let listener: ((status: { state: "starting" | "ready" | "error" | "stopped"; message: string | null }) => void) | null = null;

    window.api = {
      backend: {
        getStatus: vi.fn().mockResolvedValue({ state: "ready", message: null }),
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

    renderWithProvider(<StatusProbe />);

    expect(await screen.findByTestId("backend-state")).toHaveTextContent("ready");

    expect(listener).not.toBeNull();
    act(() => {
      listener!({ state: "error", message: "Backend exited" });
    });

    await waitFor(() => expect(screen.getByTestId("backend-state")).toHaveTextContent("error"));
  });
});
