"""Extract OCR text from Notability .note archives.

Each .note file is a ZIP containing a metadata.plist (NSKeyedArchiver)
and a HandwritingIndex/index.plist with OCR text per page.
"""

import json
import plistlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from pipeline.clinical_dictionary import get_category

NSDATE_EPOCH_OFFSET = 978307200


def _resolve_uid(objects: list, uid: plistlib.UID):
    """Resolve a UID reference, unwrapping NSString/NSMutableString dicts."""
    val = objects[uid.data]
    if isinstance(val, dict):
        # NSString in NSKeyedArchiver format: {'$class': UID, 'NS.string': 'value'}
        if "NS.string" in val:
            return val["NS.string"]
    return val


def _parse_metadata(zf: zipfile.ZipFile, inner_dir: str) -> dict:
    """Extract title, subject, and last_modified from metadata.plist."""
    with zf.open(f"{inner_dir}/metadata.plist") as f:
        data = plistlib.load(f)

    objects = data["$objects"]
    root_obj = objects[data["$top"]["root"].data]

    title = None
    subject = None
    last_modified = None

    # Resolve UID references from the root object
    # Real .note files use: noteName, noteSubject, noteModifiedDateKey
    for key, val in root_obj.items():
        if isinstance(val, plistlib.UID):
            resolved = _resolve_uid(objects, val)
            if key in ("noteTitleKey", "noteName", "notePackagePath"):
                title = resolved
            elif key in ("noteSubjectKey", "noteSubject"):
                subject = resolved
            elif key in ("noteLastModifiedDateKey", "noteModifiedDateKey"):
                if isinstance(resolved, dict) and "NS.time" in resolved:
                    ns_time = resolved["NS.time"]
                    unix_ts = ns_time + NSDATE_EPOCH_OFFSET
                    last_modified = datetime.fromtimestamp(
                        unix_ts, tz=timezone.utc
                    ).isoformat()

    return {
        "title": title or "Untitled",
        "subject": subject or "Unknown",
        "last_modified": last_modified or "",
    }


def _parse_handwriting(zf: zipfile.ZipFile, inner_dir: str) -> str:
    """Extract OCR text from HandwritingIndex/index.plist, pages in order."""
    plist_path = f"{inner_dir}/HandwritingIndex/index.plist"
    names = zf.namelist()
    if plist_path not in names:
        raise FileNotFoundError("No HandwritingIndex found")

    with zf.open(plist_path) as f:
        data = plistlib.load(f)

    pages = data.get("pages", {})
    if not pages:
        raise FileNotFoundError("No HandwritingIndex found")

    # Sort by page number (keys are strings like "1", "2", etc.)
    sorted_keys = sorted(pages.keys(), key=lambda k: int(k))
    page_texts = []
    for key in sorted_keys:
        page = pages[key]
        text = page.get("text", "")
        page_texts.append(text)

    return "\n\n".join(page_texts)


def extract_note(note_path: Path, output_dir: Path) -> dict:
    """Extract a single .note file to a raw .md file.

    Returns a result dict with success status and metadata.
    """
    try:
        with zipfile.ZipFile(note_path, "r") as zf:
            # The .note ZIP contains a single directory named after the note
            # Filter out __MACOSX and other non-content directories
            inner_dirs = {
                n.split("/")[0]
                for n in zf.namelist()
                if not n.startswith("__MACOSX") and "/" in n
            }
            if not inner_dirs:
                raise FileNotFoundError("No content directory in .note archive")
            inner_dir = next(iter(inner_dirs))

            metadata = _parse_metadata(zf, inner_dir)
            raw_text = _parse_handwriting(zf, inner_dir)

    except FileNotFoundError as e:
        return {
            "success": False,
            "file": str(note_path),
            "error": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "file": str(note_path),
            "error": f"{type(e).__name__}: {e}",
        }

    subject = metadata["subject"].strip()
    # Real .note files may store internal keys like "unsortedNotesKey"
    # instead of actual folder names — fall back to filesystem parent
    if not subject or subject.endswith("Key") or subject == "Unknown":
        subject = note_path.parent.name
    title = metadata["title"]
    default_category = get_category(subject)
    source_file = f"{subject}/{title}.note"

    front_matter = {
        "title": title,
        "subject": subject,
        "default_category": default_category,
        "source_file": source_file,
        "last_modified": metadata["last_modified"],
    }

    out_path = output_dir / subject / f"{title}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        f"---\n{yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)}---\n{raw_text}\n"
    )

    return {
        "success": True,
        "file": str(note_path),
        "title": title,
        "subject": subject,
        "category": default_category,
        "output": str(out_path),
    }


def extract_all(
    source_dir: Path, output_dir: Path, limit: int | None = None
) -> list[dict]:
    """Extract all .note files found recursively under source_dir.

    Args:
        source_dir: Root directory to search for .note files.
        output_dir: Where to write raw .md files.
        limit: Max number of files to process (None = all).

    Returns:
        List of result dicts from extract_note.
    """
    note_files = sorted(source_dir.rglob("*.note"))
    if limit is not None:
        note_files = note_files[:limit]

    results = []
    for note_path in note_files:
        result = extract_note(note_path, output_dir)
        results.append(result)

    # Write extraction log to parent of raw/ (i.e. data/notes_md/)
    failures = [r for r in results if not r["success"]]
    log = {
        "total": len(results),
        "success": len(results) - len(failures),
        "failed": len(failures),
        "failures": [
            {**f, "timestamp": datetime.now(timezone.utc).isoformat()}
            for f in failures
        ],
    }
    log_path = output_dir.parent / "extraction_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2))

    successes = len(results) - len(failures)
    print(f"Extracted {successes}/{len(results)} notes ({len(failures)} failures)")

    return results
