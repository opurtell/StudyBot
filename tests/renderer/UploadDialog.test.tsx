import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import UploadDialog from "../../src/renderer/components/UploadDialog";
import { stubWindowBackendApi, renderWithAppProvidersNoRouter } from "./testUtils";

describe("UploadDialog", () => {
  const onClose = vi.fn();
  const onUploaded = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    stubWindowBackendApi();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            extensions: [".md", ".pdf", ".txt"],
            max_size_mb: 20,
          }),
      })
    );
  });

  it("renders the dialog with title and file input", () => {
    renderWithAppProvidersNoRouter(<UploadDialog isOpen={true} onClose={onClose} onUploaded={onUploaded} />);
    expect(screen.getByText("Add Documentation")).toBeInTheDocument();
    expect(screen.getByText(/drag and drop/i)).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    renderWithAppProvidersNoRouter(<UploadDialog isOpen={false} onClose={onClose} onUploaded={onUploaded} />);
    expect(screen.queryByText("Add Documentation")).not.toBeInTheDocument();
  });

  it("shows accepted formats", async () => {
    renderWithAppProvidersNoRouter(<UploadDialog isOpen={true} onClose={onClose} onUploaded={onUploaded} />);
    expect(await screen.findByText(/\.md, \.pdf, \.txt/)).toBeInTheDocument();
  });

  it("disables upload button when no file is selected", () => {
    renderWithAppProvidersNoRouter(<UploadDialog isOpen={true} onClose={onClose} onUploaded={onUploaded} />);
    const uploadBtn = screen.getByRole("button", { name: /upload/i });
    expect(uploadBtn).toBeDisabled();
  });
});
