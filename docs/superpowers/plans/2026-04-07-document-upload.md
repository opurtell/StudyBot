# Document Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up the "+New Documentation" button in Library.tsx so users can upload Markdown, PDF, and plain-text files through the UI, which are then structured and ingested into ChromaDB automatically.

**Architecture:** Add a new `/upload` FastAPI router that accepts file uploads, saves them to a user-writable directory (`data/uploads/`), converts non-Markdown files to Markdown, then runs the existing structure-and-ingest pipeline. On the frontend, create a Modal component and an UploadDialog that provides file selection, format validation, and upload progress feedback.

**Tech Stack:** FastAPI `UploadFile`, Pydantic validation, `pypdf` for PDF text extraction, React file input with drag-and-drop, Tailwind CSS (Archival Protocol design tokens).

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/python/upload/router.py` | FastAPI router: POST `/upload`, status endpoint, accepted-formats endpoint |
| Create | `src/python/upload/extractor.py` | PDF/TXT → Markdown conversion functions |
| Create | `src/renderer/components/Modal.tsx` | Reusable overlay modal (fixed position, backdrop, close on escape/overlay click) |
| Create | `src/renderer/components/UploadDialog.tsx` | File picker, drag-and-drop zone, format validation, upload progress |
| Modify | `src/python/main.py:1-88` | Register new upload router |
| Modify | `src/python/paths.py:37` | Add `UPLOADS_DIR` and `UPLOADS_STRUCTURED_DIR` paths |
| Modify | `src/renderer/pages/Library.tsx:33-36` | Wire button to open UploadDialog |
| Modify | `src/renderer/types/api.ts` | Add `UploadResponse`, `AcceptedFormat` interfaces |
| Create | `tests/python/test_upload_router.py` | Backend upload tests |
| Create | `tests/renderer/UploadDialog.test.tsx` | Frontend upload dialog tests |

---

## Dependencies

Add `pypdf` to the Python dependencies for PDF text extraction.

---

### Task 1: Add upload directory paths

**Files:**
- Modify: `src/python/paths.py:37-38`

- [ ] **Step 1: Add UPLOADS_DIR and UPLOADS_STRUCTURED_DIR to paths.py**

In `src/python/paths.py`, after line 38 (`CLEANED_NOTES_DIR = ...`), add:

```python
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_STRUCTURED_DIR = DATA_DIR / "uploads" / "structured"
```

- [ ] **Step 2: Verify the file loads**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python && python3 -c "from paths import UPLOADS_DIR, UPLOADS_STRUCTURED_DIR; print(UPLOADS_DIR, UPLOADS_STRUCTURED_DIR)"`
Expected: prints two paths ending in `data/uploads` and `data/uploads/structured`

- [ ] **Step 3: Commit**

```bash
git add src/python/paths.py
git commit -m "feat: add upload directory paths for user-uploaded documents"
```

---

### Task 2: Create file extractor (PDF/TXT → Markdown)

**Files:**
- Create: `src/python/upload/extractor.py`
- Create: `src/python/upload/__init__.py`

- [ ] **Step 1: Create the upload package `__init__.py`**

Create `src/python/upload/__init__.py` as an empty file:

```python
```

- [ ] **Step 2: Write the failing test for text extraction**

Create `tests/python/test_upload_router.py`:

```python
from __future__ import annotations

import pytest
from pathlib import Path
from upload.extractor import extract_text, SUPPORTED_EXTENSIONS


def test_extract_text_from_plain_text(tmp_path: Path):
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("Hello world", encoding="utf-8")
    result = extract_text(txt_file)
    assert result == "Hello world"


def test_extract_text_from_markdown(tmp_path: Path):
    md_file = tmp_path / "notes.md"
    md_file.write_text("# Title\n\nSome content", encoding="utf-8")
    result = extract_text(md_file)
    assert result == "# Title\n\nSome content"


def test_extract_text_from_pdf(tmp_path: Path):
    try:
        from pypdf import PdfWriter
    except ImportError:
        pytest.skip("pypdf not installed")

    pdf_path = tmp_path / "test.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    # pypdf blank pages have no text — create a minimal PDF with text
    # Instead, test that a non-text PDF returns empty string gracefully
    writer.write(pdf_path)
    result = extract_text(pdf_path)
    assert isinstance(result, str)


def test_extract_text_unsupported_extension(tmp_path: Path):
    docx_file = tmp_path / "file.docx"
    docx_file.write_bytes(b"PK\x03\x04fake")
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(docx_file)


def test_supported_extensions_includes_key_formats():
    assert ".md" in SUPPORTED_EXTENSIONS
    assert ".txt" in SUPPORTED_EXTENSIONS
    assert ".pdf" in SUPPORTED_EXTENSIONS
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python && python3 -m pytest tests/python/test_upload_router.py -v -k "test_extract"`
Expected: FAIL — module `upload.extractor` not found

- [ ] **Step 4: Install pypdf**

Run: `pip install pypdf`

- [ ] **Step 5: Implement the extractor**

Create `src/python/upload/extractor.py`:

```python
"""Extract text from uploaded files, converting to Markdown-ready plain text."""

from pathlib import Path

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def extract_text(file_path: Path) -> str:
    """Extract text content from a supported file type.

    Returns UTF-8 text. For PDFs, concatenates all page texts.
    Raises ValueError for unsupported file types.
    """
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {suffix}. "
            f"Accepted: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if suffix == ".pdf":
        return _extract_pdf(file_path)

    # .md and .txt — read as UTF-8 text
    return file_path.read_text(encoding="utf-8")


def _extract_pdf(file_path: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python && python3 -m pytest tests/python/test_upload_router.py -v -k "test_extract"`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/python/upload/__init__.py src/python/upload/extractor.py tests/python/test_upload_router.py
git commit -m "feat: add file extractor for PDF, TXT, MD uploads"
```

---

### Task 3: Create the upload FastAPI router

**Files:**
- Create: `src/python/upload/router.py`
- Modify: `src/python/main.py:16,87`

- [ ] **Step 1: Write the failing test for the upload endpoint**

Add to `tests/python/test_upload_router.py`:

```python
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from upload import router as upload_router

client = TestClient(app)


# --- extractor tests (from Task 2) ---

def test_extract_text_from_plain_text(tmp_path: Path):
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("Hello world", encoding="utf-8")
    from upload.extractor import extract_text
    result = extract_text(txt_file)
    assert result == "Hello world"


def test_extract_text_from_markdown(tmp_path: Path):
    md_file = tmp_path / "notes.md"
    md_file.write_text("# Title\n\nSome content", encoding="utf-8")
    from upload.extractor import extract_text
    result = extract_text(md_file)
    assert result == "# Title\n\nSome content"


def test_extract_text_from_pdf(tmp_path: Path):
    try:
        from pypdf import PdfWriter
    except ImportError:
        pytest.skip("pypdf not installed")

    pdf_path = tmp_path / "test.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(pdf_path)
    from upload.extractor import extract_text
    result = extract_text(pdf_path)
    assert isinstance(result, str)


def test_extract_text_unsupported_extension(tmp_path: Path):
    docx_file = tmp_path / "file.docx"
    docx_file.write_bytes(b"PK\x03\x04fake")
    from upload.extractor import extract_text
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(docx_file)


def test_supported_extensions_includes_key_formats():
    from upload.extractor import SUPPORTED_EXTENSIONS
    assert ".md" in SUPPORTED_EXTENSIONS
    assert ".txt" in SUPPORTED_EXTENSIONS
    assert ".pdf" in SUPPORTED_EXTENSIONS


# --- router tests ---

def test_upload_markdown_file(tmp_path: Path, monkeypatch):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    monkeypatch.setattr(upload_router, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(upload_router, "UPLOADS_STRUCTURED_DIR", structured_dir)

    content = "# Cardiac Assessment\n\nKey steps for cardiac assessment."
    response = client.post(
        "/upload",
        files={"file": ("cardiac.md", io.BytesIO(content.encode("utf-8")), "text/markdown")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "cardiac.md"
    assert data["status"] == "processed"
    assert data["chunks"] >= 0


def test_upload_rejects_unsupported_format(monkeypatch, tmp_path: Path):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(upload_router, "UPLOADS_DIR", uploads_dir)

    response = client.post(
        "/upload",
        files={"file": ("image.png", io.BytesIO(b"\x89PNG"), "image/png")},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_rejects_empty_filename(monkeypatch, tmp_path: Path):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(upload_router, "UPLOADS_DIR", uploads_dir)

    response = client.post(
        "/upload",
        files={"file": ("", io.BytesIO(b"content"), "text/plain")},
    )
    assert response.status_code == 400


def test_get_accepted_formats():
    response = client.get("/upload/formats")
    assert response.status_code == 200
    data = response.json()
    assert ".md" in data["extensions"]
    assert ".pdf" in data["extensions"]
    assert ".txt" in data["extensions"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python && python3 -m pytest tests/python/test_upload_router.py -v -k "test_upload or test_get_accepted"`
Expected: FAIL — router not found

- [ ] **Step 3: Implement the upload router**

Create `src/python/upload/router.py`:

```python
"""Upload router — accept user documents, convert, structure, and ingest into ChromaDB."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from paths import UPLOADS_DIR, UPLOADS_STRUCTURED_DIR, CHROMA_DB_DIR
from upload.extractor import extract_text, SUPPORTED_EXTENSIONS
from pipeline.personal_docs.chunker import chunk_and_ingest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadResponse(BaseModel):
    filename: str
    status: str  # "processed" | "failed"
    chunks: int
    categories: list[str]
    source_type: str
    error: str | None = None


class AcceptedFormatsResponse(BaseModel):
    extensions: list[str]
    max_size_mb: int


MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def _extract_title(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return Path(fallback).stem


def _structure_and_ingest(
    text: str,
    filename: str,
    uploads_dir: Path,
    structured_dir: Path,
    db_path: Path,
) -> UploadResponse:
    """Add YAML front matter and ingest into ChromaDB.

    Uses source_type 'cpd_doc' for user uploads (tier 3, same as CPD docs).
    """
    title = _extract_title(text, filename)
    source_file = f"uploads/{filename}"
    source_type = "cpd_doc"
    categories = ["General Paramedicine"]
    last_modified = datetime.now(tz=timezone.utc).isoformat()

    # Save raw uploaded file
    raw_dir = uploads_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / filename).write_text(text, encoding="utf-8")

    # Create structured version with front matter
    structured_dir.mkdir(parents=True, exist_ok=True)
    out_path = structured_dir / filename

    front_matter = {
        "title": title,
        "source_type": source_type,
        "source_file": source_file,
        "categories": categories,
        "last_modified": last_modified,
    }
    yaml_block = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    structured = f"---\n{yaml_block}---\n{text}"
    out_path.write_text(structured, encoding="utf-8")

    # Ingest into ChromaDB
    try:
        result = chunk_and_ingest(out_path, db_path)
        return UploadResponse(
            filename=filename,
            status="processed",
            chunks=result.get("chunk_count", 0),
            categories=categories,
            source_type=source_type,
        )
    except Exception as e:
        logger.error(f"Ingestion failed for {filename}: {e}")
        return UploadResponse(
            filename=filename,
            status="failed",
            chunks=0,
            categories=categories,
            source_type=source_type,
            error=str(e),
        )


@router.post("", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Accepted: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit")

    # Save uploaded file to temp location for extraction
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = UPLOADS_DIR / f"_temp_{file.filename}"
    temp_path.write_bytes(contents)

    try:
        text = extract_text(temp_path)
    except ValueError as e:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)

    if not text.strip():
        raise HTTPException(status_code=400, detail="File appears to be empty")

    return _structure_and_ingest(
        text=text,
        filename=file.filename,
        uploads_dir=UPLOADS_DIR,
        structured_dir=UPLOADS_STRUCTURED_DIR,
        db_path=CHROMA_DB_DIR,
    )


@router.get("/formats", response_model=AcceptedFormatsResponse)
def get_accepted_formats() -> AcceptedFormatsResponse:
    return AcceptedFormatsResponse(
        extensions=sorted(SUPPORTED_EXTENSIONS),
        max_size_mb=20,
    )
```

- [ ] **Step 4: Register the router in main.py**

In `src/python/main.py`, add the import at line 16 (after the `sources_router` import):

```python
from upload.router import router as upload_router
```

Then add at line 87 (after `app.include_router(sources_router)`):

```python
app.include_router(upload_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python && python3 -m pytest tests/python/test_upload_router.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/python/upload/router.py src/python/main.py tests/python/test_upload_router.py
git commit -m "feat: add upload API endpoint for user documents"
```

---

### Task 4: Create the Modal component

**Files:**
- Create: `src/renderer/components/Modal.tsx`

- [ ] **Step 1: Write the failing test**

Create `tests/renderer/Modal.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import Modal from "../../src/renderer/components/Modal";

describe("Modal", () => {
  it("renders children when open", () => {
    render(
      <Modal isOpen={true} onClose={() => {}}>
        <p>Modal content</p>
      </Modal>
    );
    expect(screen.getByText("Modal content")).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    render(
      <Modal isOpen={false} onClose={() => {}}>
        <p>Modal content</p>
      </Modal>
    );
    expect(screen.queryByText("Modal content")).not.toBeInTheDocument();
  });

  it("calls onClose when backdrop is clicked", async () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose}>
        <p>Modal content</p>
      </Modal>
    );
    const backdrop = screen.getByRole("dialog").parentElement!;
    await userEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when Escape is pressed", async () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose}>
        <p>Modal content</p>
      </Modal>
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/renderer/Modal.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the Modal component**

Create `src/renderer/components/Modal.tsx`:

```tsx
import { type ReactNode, useEffect, useCallback } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
}

export default function Modal({ isOpen, onClose, children }: ModalProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        className="bg-surface-container-lowest rounded-lg shadow-lg max-w-lg w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/renderer/Modal.test.tsx`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/components/Modal.tsx tests/renderer/Modal.test.tsx
git commit -m "feat: add reusable Modal component with backdrop and escape dismiss"
```

---

### Task 5: Create the UploadDialog component

**Files:**
- Create: `src/renderer/components/UploadDialog.tsx`
- Modify: `src/renderer/types/api.ts` — add upload response types

- [ ] **Step 1: Add TypeScript interfaces for upload**

In `src/renderer/types/api.ts`, append at the end of the file:

```typescript
export interface UploadResponse {
  filename: string;
  status: "processed" | "failed";
  chunks: number;
  categories: string[];
  source_type: string;
  error?: string | null;
}

export interface AcceptedFormatsResponse {
  extensions: string[];
  max_size_mb: number;
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/renderer/UploadDialog.test.tsx`:

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import UploadDialog from "../../src/renderer/components/UploadDialog";
import { stubWindowBackendApi } from "./testUtils";

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
    render(<UploadDialog isOpen={true} onClose={onClose} onUploaded={onUploaded} />);
    expect(screen.getByText("Add Documentation")).toBeInTheDocument();
    expect(screen.getByText(/drag and drop/i)).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    render(<UploadDialog isOpen={false} onClose={onClose} onUploaded={onUploaded} />);
    expect(screen.queryByText("Add Documentation")).not.toBeInTheDocument();
  });

  it("shows accepted formats", async () => {
    render(<UploadDialog isOpen={true} onClose={onClose} onUploaded={onUploaded} />);
    expect(await screen.findByText(/\.md, \.pdf, \.txt/)).toBeInTheDocument();
  });

  it("disables upload button when no file is selected", () => {
    render(<UploadDialog isOpen={true} onClose={onClose} onUploaded={onUploaded} />);
    const uploadBtn = screen.getByRole("button", { name: /upload/i });
    expect(uploadBtn).toBeDisabled();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run tests/renderer/UploadDialog.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 4: Implement the UploadDialog component**

Create `src/renderer/components/UploadDialog.tsx`:

```tsx
import { useCallback, useRef, useState } from "react";
import Modal from "./Modal";
import Button from "./Button";
import { useApi } from "../hooks/useApi";
import type { AcceptedFormatsResponse } from "../types/api";
import { apiPost } from "../lib/apiClient";

interface UploadDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onUploaded: () => void;
}

export default function UploadDialog({ isOpen, onClose, onUploaded }: UploadDialogProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: formats } = useApi<AcceptedFormatsResponse>("/upload/formats", 1);

  const acceptedExtensions = formats?.extensions ?? [".md", ".pdf", ".txt"];
  const acceptString = acceptedExtensions.join(",");

  const validateFile = useCallback(
    (file: File): string | null => {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (!acceptedExtensions.includes(ext)) {
        return `Unsupported format: ${ext}. Accepted: ${acceptedExtensions.join(", ")}`;
      }
      return null;
    },
    [acceptedExtensions]
  );

  const handleFileSelect = useCallback(
    (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        setSelectedFile(null);
        return;
      }
      setError(null);
      setSelectedFile(file);
    },
    [validateFile]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect]
  );

  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;
    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch("http://127.0.0.1:7777/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || `Upload failed (${response.status})`);
      }

      setSelectedFile(null);
      onUploaded();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [selectedFile, onUploaded, onClose]);

  const handleClose = useCallback(() => {
    if (!uploading) {
      setSelectedFile(null);
      setError(null);
      onClose();
    }
  }, [uploading, onClose]);

  return (
    <Modal isOpen={isOpen} onClose={handleClose}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-headline text-display-sm text-primary">
          Add Documentation
        </h3>
      </div>

      <div
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors duration-200
          ${dragOver ? "border-primary bg-primary/5" : "border-outline-variant/20 hover:border-outline-variant/40"}
        `}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <span className="material-symbols-outlined text-3xl text-on-surface-variant mb-2 block">
          upload_file
        </span>
        <p className="font-body text-body-md text-on-surface-variant mb-1">
          {selectedFile ? selectedFile.name : "Drag and drop a file, or click to browse"}
        </p>
        <p className="font-mono text-[10px] text-on-surface-variant">
          Accepted: {acceptedExtensions.join(", ")}
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept={acceptString}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileSelect(file);
          }}
        />
      </div>

      {error && (
        <p className="font-body text-body-sm text-error mt-3">{error}</p>
      )}

      {selectedFile && (
        <p className="font-body text-body-sm text-on-surface-variant mt-3">
          {(selectedFile.size / 1024).toFixed(1)} KB
        </p>
      )}

      <div className="flex justify-end gap-3 mt-6">
        <Button variant="tertiary" onClick={handleClose} disabled={uploading}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
        >
          {uploading ? "Uploading..." : "Upload"}
        </Button>
      </div>
    </Modal>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run tests/renderer/UploadDialog.test.tsx`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/renderer/components/UploadDialog.tsx src/renderer/types/api.ts tests/renderer/UploadDialog.test.tsx
git commit -m "feat: add UploadDialog with drag-and-drop and format validation"
```

---

### Task 6: Wire up the Library button to open the UploadDialog

**Files:**
- Modify: `src/renderer/pages/Library.tsx:1-96`

- [ ] **Step 1: Add state and dialog to Library.tsx**

In `src/renderer/pages/Library.tsx`, make the following changes:

Add the import for `UploadDialog` and `useState`:

```tsx
import { useState } from "react";
import SourceCard from "../components/SourceCard";
import CleaningFeed from "../components/CleaningFeed";
import RepositoryFilter from "../components/RepositoryFilter";
import Button from "../components/Button";
import UploadDialog from "../components/UploadDialog";
import { useApi } from "../hooks/useApi";
import type { LibraryStatusResponse } from "../types/api";
```

Add dialog state after the existing `useState` declarations (after line 2, `const [feedVisible, setFeedVisible] = useState(true);`):

```tsx
const [uploadOpen, setUploadOpen] = useState(false);
```

Wire the button's `onClick` (replace lines 33-36):

```tsx
<Button variant="secondary" onClick={() => setUploadOpen(true)}>
  <span className="material-symbols-outlined text-sm">add</span>
  New Documentation
</Button>
```

Add the `UploadDialog` and `refetch` logic. Replace the `useApi` line (line 12) with:

```tsx
const { data, loading, error, refetch } = useApi<LibraryStatusResponse>("/sources", 1);
```

Add the `UploadDialog` just before the closing `</div>` of the component (before line 95, `)`):

```tsx
<UploadDialog
  isOpen={uploadOpen}
  onClose={() => setUploadOpen(false)}
  onUploaded={refetch}
/>
```

- [ ] **Step 2: Verify the full Library.tsx renders without errors**

Run: `npx vitest run tests/renderer/Library.test.tsx`
Expected: all PASS (if this test file exists; otherwise verify with `npx tsc --noEmit`)

- [ ] **Step 3: Commit**

```bash
git add src/renderer/pages/Library.tsx
git commit -m "feat: wire New Documentation button to upload dialog"
```

---

### Task 7: End-to-end smoke test

**Files:**
- No new files — manual verification

- [ ] **Step 1: Start the backend and verify the upload endpoint exists**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python && python3 -c "from main import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'upload' in r])"`
Expected: `['/upload', '/upload/formats']`

- [ ] **Step 2: Run the full backend test suite**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot/src/python && python3 -m pytest tests/python/ -v`
Expected: all PASS

- [ ] **Step 3: Run the full renderer test suite**

Run: `npx vitest run`
Expected: all PASS

- [ ] **Step 4: Commit (only if any fixes were needed)**

```bash
git add -u
git commit -m "fix: resolve issues found during upload e2e smoke test"
```
