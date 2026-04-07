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