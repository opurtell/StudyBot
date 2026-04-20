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
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    monkeypatch.setattr(upload_router, "CHROMA_DB_DIR", chroma_dir)

    def _fake_service_uploads_dir(service_id: str) -> Path:
        d = tmp_path / "services" / service_id / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(upload_router, "service_uploads_dir", _fake_service_uploads_dir)

    def _fake_chunk_and_ingest(md_path: Path, db_path: Path, collection_name: str = "paramedic_notes") -> dict:
        return {"chunk_count": 1, "source_file": str(md_path.name), "success": True}

    monkeypatch.setattr(upload_router, "chunk_and_ingest", _fake_chunk_and_ingest)

    content = "# Cardiac Assessment\n\nKey steps for cardiac assessment."
    response = client.post(
        "/upload",
        data={"service": "actas"},
        files={"file": ("cardiac.md", io.BytesIO(content.encode("utf-8")), "text/markdown")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "cardiac.md"
    assert data["status"] == "processed"
    assert data["chunks"] >= 0


def test_upload_rejects_unsupported_format(monkeypatch, tmp_path: Path):
    def _fake_service_uploads_dir(service_id: str) -> Path:
        d = tmp_path / "services" / service_id / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(upload_router, "service_uploads_dir", _fake_service_uploads_dir)

    response = client.post(
        "/upload",
        data={"service": "actas"},
        files={"file": ("image.png", io.BytesIO(b"\x89PNG"), "image/png")},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_rejects_empty_filename(monkeypatch, tmp_path: Path):
    def _fake_service_uploads_dir(service_id: str) -> Path:
        d = tmp_path / "services" / service_id / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(upload_router, "service_uploads_dir", _fake_service_uploads_dir)

    response = client.post(
        "/upload",
        data={"service": "actas"},
        files={"file": ("", io.BytesIO(b"content"), "text/plain")},
    )
    # FastAPI returns 422 for validation errors (empty filename)
    assert response.status_code in (400, 422)


def test_get_accepted_formats():
    response = client.get("/upload/formats")
    assert response.status_code == 200
    data = response.json()
    assert ".md" in data["extensions"]
    assert ".pdf" in data["extensions"]
    assert ".txt" in data["extensions"]
