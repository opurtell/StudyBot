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