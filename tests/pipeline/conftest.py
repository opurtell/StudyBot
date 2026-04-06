import os
import plistlib
import zipfile
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_output(tmp_path):
    """Provides raw/ and cleaned/ output directories."""
    raw = tmp_path / "raw"
    cleaned = tmp_path / "cleaned"
    raw.mkdir()
    cleaned.mkdir()
    return {"raw": raw, "cleaned": cleaned, "base": tmp_path}


@pytest.fixture
def build_note(tmp_path):
    """Factory that builds a minimal .note ZIP archive for testing.

    Usage:
        note_path = build_note(
            title="Week 2",
            subject="CSA236 Pharmacology",
            pages={"1": "page one text", "2": "page two text"},
        )
    """
    def _build(
        title: str = "Test Note",
        subject: str = "Test Subject",
        pages: dict[str, str] | None = None,
        include_handwriting: bool = True,
        last_modified: float = 652000000.0,  # NSDate ~2021-08-29
    ) -> Path:
        if pages is None:
            pages = {"1": "Sample OCR text for testing."}

        note_dir = tmp_path / subject
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = note_dir / f"{title}.note"

        with zipfile.ZipFile(note_path, "w") as zf:
            # metadata.plist (NSKeyedArchiver format)
            # Uses real Notability key names: noteName, noteSubject, noteModifiedDateKey
            objects = [
                "$null",
                {
                    "uuidKey": plistlib.UID(6),
                    "noteSubject": plistlib.UID(3),
                    "noteName": plistlib.UID(2),
                    "noteModifiedDateKey": plistlib.UID(4),
                    "$class": plistlib.UID(5),
                },
                title,
                subject,
                {"NS.time": last_modified, "$class": plistlib.UID(5)},
                {"$classname": "NSDate", "$classes": ["NSDate", "NSObject"]},
                "test-uuid-1234",
            ]
            metadata = {
                "$version": 100000,
                "$archiver": "NSKeyedArchiver",
                "$top": {"root": plistlib.UID(1)},
                "$objects": objects,
            }
            zf.writestr(
                f"{title}/metadata.plist",
                plistlib.dumps(metadata, fmt=plistlib.FMT_BINARY),
            )

            # HandwritingIndex/index.plist
            if include_handwriting:
                page_data = {}
                for page_num, text in pages.items():
                    page_data[page_num] = {"text": text}
                index = {
                    "version": 1,
                    "minCompatibleVersion": 1,
                    "pages": page_data,
                }
                zf.writestr(
                    f"{title}/HandwritingIndex/index.plist",
                    plistlib.dumps(index, fmt=plistlib.FMT_BINARY),
                )

        return note_path

    return _build
