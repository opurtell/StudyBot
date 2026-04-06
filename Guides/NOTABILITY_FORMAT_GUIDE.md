# Notability `.note` File Format: Agent Parsing Guide

A complete reference for AI agents converting Notability `.note` files to Markdown.

---

## 1. Overview

A `.note` file is a **ZIP archive** (store-method compression). Rename it to `.zip` or pass it directly to `unzip` — no special decompression needed. Inside is a single directory whose name matches the note title.

```
MyNote.note  →  unzip MyNote.note -d ./output
                output/
                └── MyNote/          ← note root
                    ├── Session.plist
                    ├── metadata.plist
                    ├── HandwritingIndex/
                    │   └── index.plist       ← PRIMARY OCR TEXT SOURCE
                    ├── Images/               ← embedded PNG/JPG images
                    │   ├── Image .png
                    │   ├── Image 1.png
                    │   └── ...
                    ├── PDFs/                 ← attached PDF files (by UUID)
                    │   └── <UUID>.pdf
                    ├── NBPDFIndex/           ← only present if PDFs attached
                    │   ├── PDFIndex.zip      ← nested zip, extract separately
                    │   └── NoteDocumentPDFMetadataIndex.plist
                    ├── Recordings/
                    │   └── library.plist     ← audio recording metadata
                    ├── Assets/               ← always present, usually empty
                    ├── thumb.png             ← note thumbnail (1x)
                    ├── thumb2x.png           ← thumbnails at various scales
                    ├── thumb3x.png
                    ├── thumb6x.png
                    ├── thumb8x.png
                    └── thumb12x.png
```

---

## 2. File-by-File Reference

### 2.1 `metadata.plist` — Note Identity

**Format:** NSKeyedArchiver binary plist. Read with `plutil -p`.

**Key fields (decoded):**

| plist key | Meaning |
|-----------|---------|
| `noteName` | Note title (string) |
| `noteSubject` | Notability "subject" / folder name (string) |
| `noteCreationDateKey` | NSDate (Core Data epoch: seconds since 2001-01-01) |
| `noteModifiedDateKey` | NSDate of last modification |
| `noteHasRecordingKey` | Integer bool — `1` if audio recording exists |
| `noteTags` | NSArray of tag strings (may be empty string `""`) |
| `uuidKey` | UUID string identifying the note |

**Date conversion:** NSDate epoch is Jan 1 2001. Add `978307200` to get Unix timestamp.  
Example: `664236132.68 + 978307200 = 1642543332` → 2022-01-19.

**Extraction command:**
```bash
plutil -p "Note Root/metadata.plist"
```

---

### 2.2 `HandwritingIndex/index.plist` — OCR Text (PRIMARY TEXT SOURCE)

**Format:** Standard binary plist (not NSKeyedArchiver). Read with `plutil -p`.

This is the most important file for text extraction. It contains **OCR-converted handwriting text** indexed by page number.

**Structure:**
```
{
  "minCompatibleVersion" => 7
  "pages" => {
    "1" => {
      "text" => "Heading\n- bullet point\n- another bullet\n..."
      "characterRects" => <binary: bounding boxes for each character>
      "pageContentOrigin" => [x, y]   ← coordinate offset of page content
      "returnIndexes" => {            ← character positions of line breaks
        "indexes" => [
          { "location" => 15, "length" => 1 }   ← newline at char index 15
          ...
        ]
      }
      "sha256Hash" => <binary>
    }
    "2" => { ... }
    ...
  }
}
```

**Key facts:**
- Page keys are **1-indexed strings** (`"1"`, `"2"`, ...).
- `"text"` already has `\n` line breaks embedded — directly usable.
- `returnIndexes` provides newline character positions for more precise reconstruction but the `"text"` value is sufficient for most use cases.
- `characterRects` is binary float data encoding bounding boxes — skip unless doing spatial layout analysis.
- Pages with only images (no handwriting) may have minimal or empty text.
- OCR quality varies; expect occasional character substitutions (e.g., `"8"` for `"g"`, `"1"` for `"l"`).

**Extraction command:**
```bash
plutil -p "Note Root/HandwritingIndex/index.plist"
```

**Python extraction pattern:**
```python
import plistlib, subprocess, json

# Convert to XML then parse
result = subprocess.run(
    ['plutil', '-convert', 'xml1', '-o', '-', 'HandwritingIndex/index.plist'],
    capture_output=True
)
data = plistlib.loads(result.stdout)
pages = data['pages']
for page_num in sorted(pages.keys(), key=int):
    text = pages[page_num].get('text', '')
    print(f"--- Page {page_num} ---")
    print(text)
```

---

### 2.3 `Session.plist` — Layout & Media Metadata

**Format:** GLKeyedArchiver binary plist (Notability's custom NSKeyedArchiver variant). Read with `plutil -p`.

This file encodes the full spatial document model. It is complex and uses positional object references rather than named keys. **Do not attempt full parsing** — instead extract specific fields:

**What it contains:**
- Note title (appears as a plain string in the objects array, e.g., `"Week 1 Intro and pharmacodynamics "`)
- Subject/folder name (e.g., `"CSA236 Pharmacology"`)
- Image file paths (`"Images/Image .png"`, `"Images/Image 1.png"`, etc.)
- Image position/size as CGRect strings (`"{{283, 137}, {512, 256}}"`)
- Paper layout: `paperLineStyle`, `paperIndex`, page dimensions
- App version: `NBNoteTakingSessionBundleVersionNumberKey`
- Whether the note uses reflow layout: `didBecomeReflowable`

**Useful grep patterns:**
```bash
# List all image files referenced
plutil -p Session.plist | grep '"Images/'

# Get note title and subject (plain strings in objects)
plutil -p Session.plist | grep -v "bytes = " | grep -v "CFKeyedArchiverUID" \
  | grep '=> "[A-Z][^$]*"' | grep -v NSDate

# Get paper style
plutil -p Session.plist | grep '"paperLineStyle\|paperIndex"'
```

**Image ordering:** Images appear in the objects array in the order they were inserted into the note. The filename `"Image .png"` (no number) is the first image; subsequent images are `"Image 1.png"`, `"Image 2.png"`, etc. Image ordering in the document correlates loosely with page ordering but **cannot be reliably mapped to specific pages** from `Session.plist` alone without full object graph deserialization.

---

### 2.4 `Images/` — Embedded Images

Standard PNG files (occasionally JPEG, indicated by `saveAsJPEG` flag in Session.plist).

**Naming convention:**
- `Image .png` — first image (note the space before `.png`)
- `Image 1.png`, `Image 2.png`, ... — subsequent images

**Characteristics:**
- May be screenshots, photos, or document scans pasted into the note.
- Max dimension is typically 1024px (configurable per image via `maxDimension` in Session.plist).
- May have rotation: `rotationDegrees` in Session.plist (0, 90, 180, 270).
- Captions are stored in Session.plist under `isCaptionEnabled` / `captionFontSize` — caption text is part of the typed text.

---

### 2.5 `PDFs/` — Attached PDF Files

PDFs are stored by UUID filename (e.g., `506B754F-4A38-4B2E-B367-AAAB5B781491.pdf`).

**Text extraction:** Use `pdftotext` (poppler) or `PyMuPDF`. Note that many attached PDFs in student notes are **scanned documents with no embedded text** — the `PDFTextIndex.txt` inside `NBPDFIndex` will be empty for these.

Handwriting written on top of a PDF is captured in `HandwritingIndex/index.plist` as normal OCR text.

---

### 2.6 `NBPDFIndex/` — PDF Search Index

Only present when PDFs are attached. Contains:

- `NoteDocumentPDFMetadataIndex.plist` — maps PDF UUID filenames to page numbers in the overall document
- `PDFIndex.zip` — nested ZIP; extract with `unzip` to get:
  - `NBPDFIndex/<UUID>.pdf/PDFTextIndex.txt` — extracted PDF text (empty if scanned)
  - `NBPDFIndex/<UUID>.pdf/PDFMetadataIndex.plist` — page dimensions, boxes
  - `NBPDFIndex/<UUID>.pdf/PDFLayoutIndex.nbpdflayout` — binary layout data
  - `NBPDFIndex/<UUID>.pdf/PDFImageIndex.plist` — image index for PDF pages

**Page mapping** (`NoteDocumentPDFMetadataIndex.plist`):
```
{
  "pageNumbers" => {
    "<UUID>.pdf" => [1, 1, 2, 2, 3, 3, ...]   ← each PDF page appears twice (front/back)
  }
  "pdfFilesMD5" => "<md5 hash>"
  "version" => 26
}
```

---

### 2.7 `Recordings/library.plist` — Audio Metadata

Standard plist. When `noteHasRecordingKey = 0` in metadata.plist, the recordings dict is empty:
```
{
  "application version" => "5014"
  "library-format-version" => "1.0"
  "recordings" => {}
}
```
When recordings exist, entries include filename, duration, and timestamp sync data. Audio files themselves are not stored inside the `.note` archive in exported notes.

---

## 3. Markdown Conversion Strategy

### Step 1: Extract the archive

```bash
NOTE="MyNote.note"
OUTDIR="/tmp/note_parse"
unzip -o "$NOTE" -d "$OUTDIR"
NOTE_ROOT="$OUTDIR/$(basename "$NOTE" .note)"
```

### Step 2: Read metadata

```bash
plutil -p "$NOTE_ROOT/metadata.plist"
# Extract: noteName, noteSubject, noteCreationDateKey
```

### Step 3: Extract OCR text per page

```bash
plutil -p "$NOTE_ROOT/HandwritingIndex/index.plist"
```

The `"text"` value for each page is already newline-separated. Process it directly.

### Step 4: List images

```bash
ls "$NOTE_ROOT/Images/"
# Returns: "Image .png", "Image 1.png", "Image 2.png", ...
```

Copy images to your output directory and insert Markdown image references between relevant text blocks.

### Step 5: Handle PDFs

```bash
if [ -d "$NOTE_ROOT/PDFs" ]; then
  for pdf in "$NOTE_ROOT/PDFs/"*.pdf; do
    pdftotext "$pdf" -  # or use PyMuPDF
  done
fi
```

Also check `$NOTE_ROOT/NBPDFIndex/PDFIndex.zip` for pre-extracted text.

### Step 6: Assemble Markdown

Recommended structure:

```markdown
# {noteName}

**Subject:** {noteSubject}  
**Date:** {noteCreationDate}

---

## Page 1

{OCR text from HandwritingIndex page "1"}

## Page 2

{OCR text from HandwritingIndex page "2"}

![Image](images/Image .png)

![Image 1](images/Image 1.png)

---

## Attached PDFs

{extracted PDF text if any}
```

---

## 4. Complete Python Extraction Script

```python
#!/usr/bin/env python3
"""
Converts a Notability .note file to Markdown.
Dependencies: none (uses system plutil). Optional: PyMuPDF for PDF text.
"""
import os
import re
import shutil
import zipfile
import plistlib
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

APPLE_EPOCH_OFFSET = 978307200  # seconds between Unix epoch and Apple Core Data epoch

def read_plist(path: Path) -> dict:
    """Read a binary plist using plutil, return parsed dict."""
    result = subprocess.run(
        ['plutil', '-convert', 'xml1', '-o', '-', str(path)],
        capture_output=True
    )
    return plistlib.loads(result.stdout)

def apple_date_to_iso(ns_time: float) -> str:
    """Convert NSDate timestamp to ISO 8601 string."""
    unix_ts = ns_time + APPLE_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime('%Y-%m-%d')

def extract_metadata(note_root: Path) -> dict:
    """Extract note title, subject, date from metadata.plist."""
    data = read_plist(note_root / 'metadata.plist')
    objects = data.get('$objects', [])
    
    # Find the SessionInfo object (index 1 in $objects)
    info = objects[1] if len(objects) > 1 else {}
    
    result = {'title': '', 'subject': '', 'date': '', 'has_recording': False}
    
    # Resolve UID references to string values
    def resolve(uid_ref):
        if hasattr(uid_ref, 'integer'):  # UID
            return objects[uid_ref.integer]
        return uid_ref
    
    result['title'] = resolve(info.get('noteName', '')) or ''
    result['subject'] = resolve(info.get('noteSubject', '')) or ''
    result['has_recording'] = bool(info.get('noteHasRecordingKey', 0))
    
    # Date from noteCreationDateKey
    creation = resolve(info.get('noteCreationDateKey'))
    if isinstance(creation, dict):
        ns_time = creation.get('NS.time', 0)
        result['date'] = apple_date_to_iso(ns_time)
    
    return result

def extract_ocr_text(note_root: Path) -> dict[str, str]:
    """Extract OCR text per page from HandwritingIndex/index.plist."""
    index_path = note_root / 'HandwritingIndex' / 'index.plist'
    if not index_path.exists():
        return {}
    
    data = read_plist(index_path)
    pages = data.get('pages', {})
    return {page_num: pages[page_num].get('text', '') 
            for page_num in sorted(pages.keys(), key=int)}

def list_images(note_root: Path) -> list[Path]:
    """Return image files in order (Image .png, Image 1.png, Image 2.png, ...)."""
    images_dir = note_root / 'Images'
    if not images_dir.exists():
        return []
    
    def sort_key(p: Path):
        name = p.stem  # "Image " or "Image 1" etc.
        match = re.search(r'(\d+)$', name)
        return int(match.group(1)) if match else -1
    
    return sorted(images_dir.glob('Image*'), key=sort_key)

def extract_pdf_text(note_root: Path) -> str:
    """Extract text from attached PDFs using pdftotext or PyMuPDF."""
    pdfs_dir = note_root / 'PDFs'
    if not pdfs_dir.exists():
        return ''
    
    texts = []
    for pdf in sorted(pdfs_dir.glob('*.pdf')):
        # Try NBPDFIndex pre-extracted text first
        pdf_index_text = note_root / 'NBPDFIndex' / 'PDFIndex.zip'
        # Fall back to pdftotext
        try:
            result = subprocess.run(
                ['pdftotext', str(pdf), '-'],
                capture_output=True, text=True
            )
            if result.stdout.strip():
                texts.append(result.stdout.strip())
        except FileNotFoundError:
            texts.append(f"[PDF attached: {pdf.name} — install pdftotext to extract text]")
    
    return '\n\n'.join(texts)

def note_to_markdown(note_path: str, output_dir: str) -> str:
    """
    Convert a .note file to Markdown.
    Returns the path to the generated .md file.
    """
    note_path = Path(note_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Extract archive
    extract_dir = output_dir / '_extracted'
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(note_path) as zf:
        zf.extractall(extract_dir)
    
    # Find note root (single directory inside archive)
    note_root = next(p for p in extract_dir.iterdir() if p.is_dir())
    
    # Step 2: Metadata
    meta = extract_metadata(note_root)
    title = meta['title'] or note_path.stem
    
    # Step 3: OCR text
    ocr_pages = extract_ocr_text(note_root)
    
    # Step 4: Images — copy to output
    images = list_images(note_root)
    images_out = output_dir / 'images'
    images_out.mkdir(exist_ok=True)
    for img in images:
        shutil.copy2(img, images_out / img.name)
    
    # Step 5: PDF text
    pdf_text = extract_pdf_text(note_root)
    
    # Step 6: Assemble Markdown
    lines = [
        f'# {title}',
        '',
        f'**Subject:** {meta["subject"]}  ',
        f'**Date:** {meta["date"]}',
        '',
        '---',
        '',
    ]
    
    total_pages = len(ocr_pages)
    for page_num, text in ocr_pages.items():
        if total_pages > 1:
            lines.append(f'## Page {page_num}')
            lines.append('')
        if text.strip():
            lines.append(text.strip())
            lines.append('')
    
    # Insert images after text (page-to-image mapping is not reliable from metadata)
    if images:
        lines.append('## Images')
        lines.append('')
        for img in images:
            lines.append(f'![{img.stem}](images/{img.name})')
            lines.append('')
    
    if pdf_text:
        lines.append('## Attached PDF Content')
        lines.append('')
        lines.append(pdf_text)
        lines.append('')
    
    md_content = '\n'.join(lines)
    
    # Write output
    safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
    md_path = output_dir / f'{safe_title}.md'
    md_path.write_text(md_content, encoding='utf-8')
    
    # Cleanup extracted dir
    shutil.rmtree(extract_dir)
    
    return str(md_path)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 parse_note.py <input.note> <output_dir>")
        sys.exit(1)
    result = note_to_markdown(sys.argv[1], sys.argv[2])
    print(f"Written: {result}")
```

---

## 5. Batch Conversion (All Notes in a Folder Tree)

```bash
#!/bin/bash
# batch_convert.sh <notes_root> <output_root>
# Preserves subject/folder hierarchy.
NOTES_ROOT="$1"
OUTPUT_ROOT="$2"

find "$NOTES_ROOT" -name "*.note" | while read -r note; do
    # Reconstruct subject hierarchy
    rel_path="${note#$NOTES_ROOT/}"
    subject_dir=$(dirname "$rel_path")
    note_name=$(basename "$note" .note)
    out_dir="$OUTPUT_ROOT/$subject_dir/$note_name"
    
    python3 parse_note.py "$note" "$out_dir"
    echo "Converted: $note → $out_dir"
done
```

---

## 6. Pandoc Conversion

Once you have Markdown output, use pandoc for further format conversion:

```bash
# Markdown → PDF (requires LaTeX)
pandoc MyNote.md -o MyNote.pdf --pdf-engine=xelatex

# Markdown → DOCX
pandoc MyNote.md -o MyNote.docx

# Markdown → HTML
pandoc MyNote.md -o MyNote.html --standalone

# Batch: all Markdown files → DOCX
find output/ -name "*.md" | while read md; do
    pandoc "$md" -o "${md%.md}.docx"
done
```

**Pandoc note:** Images must be in paths relative to the Markdown file. The script above places them in `images/` relative to the `.md` file, which pandoc handles automatically.

---

## 7. Known Limitations & Edge Cases

| Situation | Behaviour |
|-----------|-----------|
| Handwriting-only notes | `HandwritingIndex/index.plist` contains OCR text; may have recognition errors |
| Typed text in Notability | Also stored in `HandwritingIndex` (Notability indexes typed text for search the same way) |
| Images on specific pages | Page-to-image mapping requires parsing the full `Session.plist` object graph — not documented here; treat all images as note-level content |
| Scanned PDFs | `PDFTextIndex.txt` will be empty; annotated handwriting over PDF still appears in `HandwritingIndex` |
| Audio recordings | Audio files are NOT inside the `.note` archive for exported notes; only metadata in `library.plist` |
| Multi-page notes | Each page is a separate key in `HandwritingIndex/pages` |
| Empty notes / blank pages | Pages with no handwriting may be absent from `HandwritingIndex/pages` entirely |
| RTF companion files | Some notes export an accompanying `.rtf` file — these may be empty shells; the `.note` is authoritative |
| `Assets/` directory | Always present, found empty in all examined samples; likely used for custom stickers/assets |
| `thumb*.png` files | Thumbnails at various DPI scales — useful for preview, not for content extraction |

---

## 8. Quick Reference: File Priority for Extraction

| Content type | Primary source | Fallback |
|-------------|---------------|---------|
| Note title | `metadata.plist` → `noteName` | `Session.plist` (string in objects array) |
| Subject/folder | `metadata.plist` → `noteSubject` | Parent directory name |
| Creation date | `metadata.plist` → `noteCreationDateKey` | File system mtime |
| Handwritten text | `HandwritingIndex/index.plist` → `pages[N].text` | None |
| Typed text | `HandwritingIndex/index.plist` → `pages[N].text` | None |
| Images | `Images/` directory | — |
| PDF content | `NBPDFIndex/PDFIndex.zip` → `PDFTextIndex.txt` | `pdftotext` on `PDFs/<UUID>.pdf` |
| Tags | `metadata.plist` → `noteTags` | — |
