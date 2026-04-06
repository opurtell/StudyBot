# Notability → RAG Pipeline: Claude Code Agent Guide

**Purpose:** This document is a complete, self-contained briefing for a Claude Code agent to build, test, and run the full `.note` → ChromaDB pipeline on the paramedic study notes in this directory. Read it from top to bottom before taking any action. The format guide for `.note` file parsing is in `NOTABILITY_FORMAT_GUIDE.md` — refer to it for all extraction details.

---

## Directory Context

The `.note` source files live under the main project tree. **476 `.note` files** across 10 top-level semester/subject folders (including one duplicate — see gotchas).

```
studyBotcode/
├── Guides/
│   ├── NOTABILITY_FORMAT_GUIDE.md         ← authoritative .note parsing reference
│   └── PIPELINE_AGENT_GUIDE.md            ← this file
├── docs/notabilityNotes/
│   ├── noteDocs/
│   │   └── drive-download-.../            ← all .note files
│   │       ├── CAA Medical emergencies 1/         (2 files)
│   │       ├── CNA308 Legal and Ethical/          (1 file)
│   │       ├── CSA236 Pharmacology/               (10 files)
│   │       ├── Paramedics 2021 sem 1/             (71 files, 5 subject subfolders)
│   │       ├── Paramedics 2021 sem 1 /            (68 files — DUPLICATE w/ trailing space)
│   │       ├── Paramedics 2021 sem 2/             (98 files, 5 subject subfolders)
│   │       ├── Paramedics 2021 sem 3/             (67 files, 4 subject subfolders)
│   │       ├── Paramedics 2022 Sem 1/             (71 files, 3 subject subfolders)
│   │       ├── Paramedics 2022 Sem 2/             (49 files, 3 subject subfolders)
│   │       └── Paramedics 2022 Sem 3/             (36 files, 3 subject subfolders)
│   └── mdDocs/                            ← output dir for converted markdown
├── src/python/pipeline/                   ← pipeline source code
│   ├── cleaning_prompt.md
│   └── clinical_dictionary.py
└── data/
    ├── notes_md/
    │   ├── raw/                           ← extracted raw markdown (pre-cleaning)
    │   └── cleaned/                       ← OCR-cleaned markdown (post-cleaning)
    └── chroma_db/                         ← ChromaDB persistence directory
```

**Subject folders within each semester** (28 total across all semesters):

| Semester | Subjects |
|----------|----------|
| 2021 sem 1 | CAA107 Principles of Paramedic Practice, CAA209 Evidence Based Research Methods, CAA210 Mental Health Care, CNA151 Health and Health Care in Australia, Orientation |
| 2021 sem 2 | CAA108 Paramedic Practice 2, CNA146 Aging, CNA156 Aboriginal, CNA157 Diversity, CXA107 Intro to Bioscience |
| 2021 sem 3 | CAA109 Placement, CAA205 Med Emergencies, CNA308 Ethics and Law, CSA236 Pharmacology |
| 2022 Sem 1 | Arts and Dementia, CAA206 Med Emerg 2, CXA206 Bio 1 |
| 2022 Sem 2 | CAA306 Trauma, CXA309 Health Services, CXA310 Bio 2 |
| 2022 Sem 3 | CAA305 Environmental Emergencies, CAA307 Obstetrics and Paediatrics, CAA309 Professional Development |
| Top-level | CAA Medical Emergencies 1, CNA308 Legal and Ethical, CSA236 Pharmacology |

---

## When to Use Subagents — Decision Table

Use this table to decide when to spawn a subagent vs. doing the work inline.

| Situation | Agent Type | Thoroughness | Reason |
|---|---|---|---|
| First time exploring the `.note` directory tree to count files and understand folder structure | **Explore** | quick | Fast read-only scan, no writes needed |
| Verifying that `plistlib` correctly decodes a specific `.note` file before writing code | **Explore** | quick | Single-file read + targeted grep |
| Researching the best ChromaDB collection schema for medical RAG (chunking strategy, metadata fields) | **Explore** | medium | Multi-source question, no code changes |
| Planning the full architecture before writing any code in a new project | **Plan** | — | Architectural decisions with trade-offs |
| Deeply auditing every `.note` file across all 4 subject folders for structural anomalies | **Explore** | very thorough | Large multi-directory sweep |
| Writing code for any single stage (extractor, cleaner, structurer, chunker) | **None** — do it inline | — | Focused coding task; subagent adds overhead |
| Running tests and validating output after writing code | **None** — use Bash inline | — | Sequential dependency on code you just wrote |
| Investigating a bug in plist parsing across many note files | **general-purpose** | — | Multi-step debug loop with file reads + bash |

**Key rule:** Never spawn an agent for a task you can complete with 1–3 tool calls. Subagents are for open-ended research or large sweeps you would otherwise spend 10+ tool calls on.

---

## Prerequisites

Before writing any code, run these checks. If a check fails, install the missing tool before proceeding — do not work around it.

```bash
# Python 3.10+
python3 --version

# plutil (ships with macOS, should always be present)
which plutil

# pip packages (install if missing)
pip3 install anthropic langchain-text-splitters chromadb

# Verify anthropic key is set
echo $ANTHROPIC_API_KEY
```

If `ANTHROPIC_API_KEY` is not set, tell the user to run:
```bash
export ANTHROPIC_API_KEY="your-key-here"
```
Do not proceed without it — the cleaning agent requires it.

---

## Stage 1 — Extractor (`src/extractor.py`)

**What it does:** Opens a `.note` file (ZIP archive), reads `HandwritingIndex/index.plist` for OCR text and `metadata.plist` for title/subject/date. Returns a plain Python dict.

**Critical facts from `NOTABILITY_FORMAT_GUIDE.md`:**
- `metadata.plist` uses `NSKeyedArchiver`. Navigate its `$objects` array using `plistlib` UID references.
- `HandwritingIndex/index.plist` is a standard plist. Pages are 1-indexed string keys.
- NSDate epoch offset: `+978307200` seconds from Unix epoch.
- The `noteSubject` field in metadata contains the Notability folder name (e.g., `"CSA236 Pharmacology"`) — use this for category assignment.

```python
# pipeline/src/extractor.py

import zipfile
import plistlib
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

APPLE_EPOCH_OFFSET = 978307200


def _read_plist_from_bytes(data: bytes) -> dict:
    """Convert binary plist bytes to dict via plutil."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix='.plist', delete=False) as f:
        f.write(data)
        tmp = f.name
    result = subprocess.run(
        ['plutil', '-convert', 'xml1', '-o', '-', tmp],
        capture_output=True
    )
    os.unlink(tmp)
    return plistlib.loads(result.stdout)


def _apple_date_to_iso(ns_time: float) -> str:
    unix_ts = ns_time + APPLE_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime('%Y-%m-%d')


def _extract_metadata(zf: zipfile.ZipFile, note_root: str) -> dict:
    """Parse metadata.plist from inside the zip."""
    meta_path = f"{note_root}/metadata.plist"
    raw = zf.read(meta_path)
    data = _read_plist_from_bytes(raw)
    objects = data.get('$objects', [])

    def resolve(ref):
        """Follow a UID reference into the $objects array."""
        if hasattr(ref, 'data'):          # plistlib UID in Python 3.8+
            return objects[int.from_bytes(ref.data, 'big')]
        if isinstance(ref, plistlib.UID): # plistlib UID
            return objects[ref.integer]
        return ref

    info = objects[1] if len(objects) > 1 else {}

    title = ''
    subject = ''
    date_str = ''

    if isinstance(info, dict):
        title_ref = info.get('noteName')
        subject_ref = info.get('noteSubject')
        date_ref = info.get('noteCreationDateKey')
        modified_ref = info.get('noteModifiedDateKey')

        title = resolve(title_ref) if title_ref is not None else ''
        subject = resolve(subject_ref) if subject_ref is not None else ''

        # Prefer modified date for last_modified field
        date_obj = resolve(modified_ref) if modified_ref is not None else resolve(date_ref) if date_ref is not None else None
        if isinstance(date_obj, dict):
            ns_time = date_obj.get('NS.time', 0)
            date_str = _apple_date_to_iso(ns_time)

    # Fallback: scan objects for non-empty, non-system strings
    if not title:
        for obj in objects:
            if isinstance(obj, str) and obj and not obj.startswith('$') and obj != 'unsortedNotesKey':
                title = obj
                break

    return {'title': str(title), 'subject': str(subject), 'last_modified': date_str}


def _extract_ocr_text(zf: zipfile.ZipFile, note_root: str) -> str:
    """Parse HandwritingIndex/index.plist, return all pages joined."""
    hw_path = f"{note_root}/HandwritingIndex/index.plist"
    try:
        raw = zf.read(hw_path)
    except KeyError:
        return ''

    data = _read_plist_from_bytes(raw)
    pages = data.get('pages', {})

    page_texts = []
    for page_num in sorted(pages.keys(), key=lambda x: int(x)):
        text = pages[page_num].get('text', '').strip()
        if text:
            page_texts.append(text)

    return '\n\n'.join(page_texts)


def extract_note(note_path: str) -> dict:
    """
    Extract content from a .note file.

    Returns:
        {
            'title': str,
            'subject': str,          # Notability folder name, e.g. "CSA236 Pharmacology"
            'last_modified': str,    # ISO date string
            'raw_text': str,         # OCR text, all pages concatenated
            'source_file': str,      # basename of the .note file
        }
    """
    path = Path(note_path)
    with zipfile.ZipFile(path) as zf:
        # Find note root directory name (top-level dir inside the zip)
        names = zf.namelist()
        note_root = names[0].split('/')[0]

        metadata = _extract_metadata(zf, note_root)
        raw_text = _extract_ocr_text(zf, note_root)

    # Use filename as title fallback
    if not metadata['title']:
        metadata['title'] = path.stem

    return {
        **metadata,
        'raw_text': raw_text,
        'source_file': path.name,
    }
```

**Testing Stage 1:** After writing this file, immediately test it:
```bash
cd pipeline
python3 -c "
from src.extractor import extract_note
import json
result = extract_note('docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3/CSA236 Pharmacology/Basic principles revision.note')
print(json.dumps({k: v[:200] if k == 'raw_text' else v for k, v in result.items()}, indent=2))
"
```
Expected: `title` = `"Basic principles revision"`, `subject` = `"unsortedNotesKey"` or similar, `raw_text` starts with pharmacology content. If `raw_text` is empty, check the `HandwritingIndex/index.plist` path inside the zip — use `zipfile.ZipFile(...).namelist()` to inspect.

---

## Stage 2 — Clinical Dictionary (`clinical_dictionary.py`)

This is a grounding dictionary passed to the LLM. It must be paramedicine-specific. Write it as a module so it can be imported and extended.

```python
# pipeline/clinical_dictionary.py

CLINICAL_DICTIONARY: dict[str, list[str]] = {
    "Pharmacology": [
        # Concepts
        "pharmacodynamics", "pharmacokinetics", "agonist", "partial agonist",
        "antagonist", "competitive antagonist", "irreversible antagonist",
        "affinity", "efficacy", "potency", "therapeutic index", "half-life",
        "bioavailability", "first-pass metabolism", "volume of distribution",
        "ion trapping", "protein binding", "steady state", "loading dose",
        "maintenance dose", "tolerance", "tachyphylaxis",
        # Routes
        "IV", "IM", "SC", "SL", "IN", "IO", "PO", "PR", "ETT",
        "intravenous", "intramuscular", "subcutaneous", "sublingual",
        "intranasal", "intraosseous",
        # Units
        "mg", "mcg", "µg", "mL", "L", "mg/kg", "mcg/kg", "mg/hr",
        # Receptors
        "alpha-1", "alpha-2", "beta-1", "beta-2", "muscarinic",
        "nicotinic", "dopaminergic", "opioid", "GABA",
        # ACTAS Drugs
        "adrenaline", "epinephrine", "noradrenaline", "metaraminol",
        "morphine", "fentanyl", "ketamine", "midazolam", "diazepam",
        "naloxone", "flumazenil", "salbutamol", "ipratropium",
        "adenosine", "amiodarone", "lignocaine", "atropine",
        "aspirin", "GTN", "glyceryl trinitrate", "dextrose",
        "thiamine", "ondansetron", "droperidol", "haloperidol",
        "hydrocortisone", "adrenaline auto-injector",
        "tranexamic acid", "TXA", "heparin",
    ],
    "Cardiac": [
        "ventricular fibrillation", "VF", "ventricular tachycardia", "VT",
        "supraventricular tachycardia", "SVT", "atrial fibrillation", "AF",
        "pulseless electrical activity", "PEA", "asystole",
        "STEMI", "NSTEMI", "ACS", "acute coronary syndrome",
        "defibrillation", "cardioversion", "synchronized cardioversion",
        "12-lead ECG", "sinus rhythm", "sinus bradycardia", "sinus tachycardia",
        "heart block", "first-degree", "second-degree", "third-degree",
        "Wolff-Parkinson-White", "WPW", "LBBB", "RBBB",
        "ST elevation", "ST depression", "T-wave inversion",
        "cardiac output", "stroke volume", "preload", "afterload", "contractility",
        "systolic", "diastolic", "mean arterial pressure", "MAP",
    ],
    "Trauma": [
        "tourniquet", "haemorrhage", "hemorrhage", "haemostasis",
        "tension pneumothorax", "needle thoracostomy", "needle decompression",
        "open pneumothorax", "haemothorax", "flail chest",
        "TCCC", "tactical combat casualty care",
        "junctional haemorrhage", "pelvic binder",
        "cervical collar", "spinal immobilisation",
        "GCS", "Glasgow Coma Scale", "AVPU",
        "mechanism of injury", "MOI",
        "primary survey", "secondary survey", "ABCDE",
        "airway", "breathing", "circulation", "disability", "exposure",
    ],
    "Airway": [
        "RSI", "rapid sequence intubation", "rapid sequence induction",
        "laryngoscopy", "direct laryngoscopy", "video laryngoscopy",
        "endotracheal intubation", "ETI", "ETT",
        "supraglottic airway", "SGA", "LMA", "laryngeal mask airway",
        "i-gel", "King LT", "iGel",
        "BVM", "bag-valve-mask", "bag mask ventilation",
        "cricothyrotomy", "surgical airway",
        "CPAP", "BiPAP", "PEEP", "positive end-expiratory pressure",
        "SpO2", "oxygen saturation", "EtCO2", "end-tidal CO2", "waveform capnography",
        "sellick manoeuvre", "cricoid pressure", "BURP",
        "succinylcholine", "suxamethonium", "rocuronium", "vecuronium",
    ],
    "Medical Emergencies": [
        "anaphylaxis", "anaphylactic", "adrenaline auto-injector", "EpiPen",
        "asthma", "bronchospasm", "status asthmaticus",
        "COPD", "chronic obstructive pulmonary disease",
        "pulmonary oedema", "APO", "acute pulmonary oedema",
        "hypoglycaemia", "hyperglycaemia", "DKA", "diabetic ketoacidosis",
        "HHS", "hyperosmolar hyperglycaemic state",
        "seizure", "status epilepticus", "eclampsia",
        "stroke", "TIA", "transient ischaemic attack", "FAST", "BE-FAST",
        "sepsis", "SIRS", "systemic inflammatory response syndrome",
        "meningitis", "encephalitis",
    ],
    "General": [
        "paramedic", "ACTAS", "ALS", "BLS",
        "protocol", "guideline", "standing order",
        "patient assessment", "vital signs",
        "blood pressure", "heart rate", "respiratory rate",
        "temperature", "blood glucose level", "BGL",
        "pain score", "NRS", "numerical rating scale",
    ],
}

# Map Notability subject folder names to categories
SUBJECT_TO_CATEGORY: dict[str, str] = {
    "CSA236 Pharmacology": "Pharmacology",
    "CAA205 Med Emergencies": "Medical Emergencies",
    "CAA109 placement": "General",
    "CNA308 Ethics and Law": "General",
    "unsortedNotesKey": "General",  # Notability default for uncategorised notes
}


def get_category(subject: str) -> str:
    """Map a Notability subject string to a pipeline category."""
    return SUBJECT_TO_CATEGORY.get(subject, "General")


def get_dictionary_for_category(category: str) -> list[str]:
    """Return the clinical terms for a given category, plus General terms."""
    terms = CLINICAL_DICTIONARY.get(category, [])
    if category != "General":
        terms = terms + CLINICAL_DICTIONARY["General"]
    return sorted(set(terms))
```

---

## Stage 3 — Medical Cleaning Agent (`src/cleaning_agent.py`)

**Design decisions:**
- Uses Claude Opus 4.6 (`claude-opus-4-6`). Do not downgrade to Haiku or Sonnet — drug name OCR errors are high-stakes and require the strongest reasoning.
- The system prompt is strict: fix only, never rephrase or add.
- `[REVIEW_REQUIRED: <text>]` is the low-confidence flag. The LLM is instructed to use this when it cannot confidently correct a value.
- The dictionary is passed in the user message, not the system prompt, so it can vary per call.

```python
# pipeline/src/cleaning_agent.py

import re
import anthropic
from clinical_dictionary import get_dictionary_for_category

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a medical transcription corrector for Australian paramedic study notes (ACTAS protocol).
Your ONLY job is to fix OCR transcription errors caused by handwriting recognition. You must NOT rephrase,
summarise, reorder, or add any content.

Rules — follow exactly:
1. Fix obvious OCR errors using the clinical dictionary as the source of truth for correct spellings.
   Common OCR errors: "1" for "l", "0" for "o", "rn" for "m", missing spaces, transposed characters,
   garbled word endings (e.g. "Pharmace dynamics" → "Pharmacodynamics").
2. Preserve ALL original structure without exception: line breaks, bullet points (-, •, *), numbering
   (i., ii., 1., 2.), indentation, blank lines between sections.
3. If a drug dose, drug name, or critical clinical value is garbled and you cannot confidently correct it,
   wrap ONLY that token in [REVIEW_REQUIRED: <original text>] and leave the surrounding text unchanged.
   Use this sparingly — only when genuinely uncertain.
4. Do NOT correct grammar, spelling of non-clinical words, or sentence structure.
5. Do NOT add headings, summaries, or explanatory text.
6. Return ONLY the corrected text. No preamble, no explanation."""


def clean_text(raw_text: str, category: str) -> str:
    """
    Run the OCR cleaning pass on raw text.

    Args:
        raw_text: OCR-extracted text from a .note file.
        category: Clinical category (e.g. "Pharmacology") for dictionary selection.

    Returns:
        Cleaned text with [REVIEW_REQUIRED: ...] tags where uncertain.
    """
    terms = get_dictionary_for_category(category)
    dictionary_block = "\n".join(f"  - {t}" for t in terms)

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Category: {category}\n\n"
                f"Clinical Dictionary (correct terms for this category):\n{dictionary_block}\n\n"
                f"--- RAW OCR TEXT ---\n{raw_text}\n--- END ---\n\n"
                "Return the corrected text only."
            )
        }]
    )
    return response.content[0].text


def extract_review_flags(cleaned_text: str) -> list[dict]:
    """
    Extract all [REVIEW_REQUIRED: ...] tags from cleaned text.

    Returns list of dicts: {'flagged_text': str, 'start': int, 'end': int}
    """
    return [
        {
            'flagged_text': m.group(1),
            'start': m.start(),
            'end': m.end(),
        }
        for m in re.finditer(r'\[REVIEW_REQUIRED:\s*([^\]]+)\]', cleaned_text)
    ]
```

---

## Stage 4 — Markdown Structurer (`src/structurer.py`)

**What it does:** Takes cleaned text + metadata and produces a structured `.md` file with YAML front matter. This is rules-based — no LLM.

**YAML front matter is required** because ChromaDB metadata is attached per-chunk, but the `.md` files also need to be human-readable and parseable by tools like Obsidian.

```python
# pipeline/src/structurer.py

import re
from pathlib import Path


def structure_as_markdown(cleaned_text: str, metadata: dict) -> str:
    """
    Wrap cleaned text in structured Markdown with YAML front matter.

    Args:
        cleaned_text: Output of cleaning_agent.clean_text()
        metadata: Dict with keys: title, subject, category, last_modified,
                  source_file, review_flag_count

    Returns:
        Full Markdown string ready for writing to disk.
    """
    title = metadata.get('title', 'Untitled')
    subject = metadata.get('subject', '')
    category = metadata.get('category', 'General')
    last_modified = metadata.get('last_modified', '')
    source_file = metadata.get('source_file', '')
    flag_count = metadata.get('review_flag_count', 0)

    yaml_header = (
        "---\n"
        f'title: "{_escape_yaml(title)}"\n'
        f'subject: "{_escape_yaml(subject)}"\n'
        f'category: "{category}"\n'
        f'source_file: "{source_file}"\n'
        f'last_modified: "{last_modified}"\n'
        f'review_flags: {flag_count}\n'
        "---"
    )

    # Strip the note title from text if it's a redundant first line
    text = cleaned_text.strip()
    first_line = text.splitlines()[0].strip() if text else ''
    if first_line.lower() == title.lower():
        text = '\n'.join(text.splitlines()[1:]).strip()

    return f"{yaml_header}\n\n# {title}\n\n{text}\n"


def write_markdown(content: str, output_dir: str, title: str) -> str:
    """Write structured Markdown to disk. Returns the output file path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
    out_path = out / f"{safe_name}.md"
    out_path.write_text(content, encoding='utf-8')
    return str(out_path)


def _escape_yaml(s: str) -> str:
    return s.replace('"', '\\"')
```

---

## Stage 5 — Chunker + ChromaDB Ingestion (`src/chunker.py`)

**Chunking strategy:** `RecursiveCharacterTextSplitter` from `langchain-text-splitters`. It splits on `\n\n` first (paragraph boundaries), then `\n` (line breaks), then sentences. This preserves bullet point integrity better than token-count splitters, which can cut mid-list.

**Chunk size:** 800 characters with 100-character overlap. At ~4 chars/token this is ~200 tokens per chunk — conservative enough to preserve full drug dosing lines without truncation.

**ChromaDB note:** Use `PersistentClient` so the vector store survives between runs. The collection name is `"paramedic_notes"`. Do not recreate it on every run — use `get_or_create_collection`.

```python
# pipeline/src/chunker.py

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path

SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def get_collection(chroma_dir: str) -> chromadb.Collection:
    """Return (or create) the persistent ChromaDB collection."""
    client = chromadb.PersistentClient(path=chroma_dir)
    return client.get_or_create_collection(
        name="paramedic_notes",
        metadata={"hnsw:space": "cosine"},
    )


def ingest(
    structured_md: str,
    metadata: dict,
    collection: chromadb.Collection,
) -> int:
    """
    Chunk and ingest a structured Markdown document.

    Args:
        structured_md: Output of structurer.structure_as_markdown()
        metadata: Dict with source_file, last_modified, category, source_file
        collection: ChromaDB collection

    Returns:
        Number of chunks ingested.
    """
    chunks = SPLITTER.split_text(structured_md)

    ids = []
    documents = []
    metadatas = []

    # Use source_file as a stable base for chunk IDs
    base_id = metadata['source_file'].replace(' ', '_').replace('.note', '')

    for i, chunk in enumerate(chunks):
        chunk_id = f"{base_id}_chunk_{i:04d}"

        # Delete existing chunk if re-running on the same note
        try:
            collection.delete(ids=[chunk_id])
        except Exception:
            pass

        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "source_file": metadata['source_file'],
            "last_modified": metadata.get('last_modified', ''),
            "category": metadata.get('category', 'General'),
            "chunk_index": i,
            "has_review_flag": "[REVIEW_REQUIRED" in chunk,
        })

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks)
```

---

## Stage 6 — Full Pipeline Entrypoint (`src/pipeline.py`)

```python
# pipeline/src/pipeline.py

import json
from pathlib import Path

from extractor import extract_note
from cleaning_agent import clean_text, extract_review_flags
from structurer import structure_as_markdown, write_markdown
from chunker import get_collection, ingest
from clinical_dictionary import get_category


def process_note(
    note_path: str,
    output_dir: str,
    chroma_dir: str,
    collection,
    dry_run: bool = False,
) -> dict:
    """
    Run the full pipeline on a single .note file.

    Args:
        note_path:   Absolute path to the .note file.
        output_dir:  Directory to write cleaned .md files.
        chroma_dir:  ChromaDB persistence directory.
        collection:  ChromaDB collection (pass in to reuse across calls).
        dry_run:     If True, skip ChromaDB ingestion and file writes.

    Returns:
        Summary dict with title, category, chunk_count, review_flags.
    """
    # Stage 1: Extract
    extracted = extract_note(note_path)
    category = get_category(extracted['subject'])
    extracted['category'] = category

    print(f"  [1/4] Extracted: {extracted['title']} ({category})")

    # Stage 2: Clean
    cleaned = clean_text(extracted['raw_text'], category)
    flags = extract_review_flags(cleaned)
    if flags:
        print(f"  [2/4] Cleaned — {len(flags)} item(s) flagged for review")
    else:
        print(f"  [2/4] Cleaned — no flags")

    # Stage 3: Structure
    metadata = {
        'title': extracted['title'],
        'subject': extracted['subject'],
        'category': category,
        'source_file': extracted['source_file'],
        'last_modified': extracted['last_modified'],
        'review_flag_count': len(flags),
    }
    structured_md = structure_as_markdown(cleaned, metadata)

    # Stage 4: Write + Ingest
    if not dry_run:
        md_path = write_markdown(structured_md, output_dir, extracted['title'])
        chunk_count = ingest(structured_md, metadata, collection)
        print(f"  [4/4] Written: {md_path} | Chunks: {chunk_count}")
    else:
        md_path = None
        chunk_count = 0
        print(f"  [4/4] Dry run — skipping write and ingest")

    return {
        'title': extracted['title'],
        'category': category,
        'source_file': extracted['source_file'],
        'md_path': md_path,
        'chunk_count': chunk_count,
        'review_flags': [f['flagged_text'] for f in flags],
    }
```

---

## Run Script (`run.py`)

This is the CLI entrypoint. It accepts a directory of `.note` files (or a single file) and runs the full pipeline.

```python
#!/usr/bin/env python3
# pipeline/run.py
"""
Usage:
    # Process all .note files in a directory tree
    python3 run.py --input "docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3" --output ./data/notes_md/raw --chroma ./data/chroma_db

    # Process a single file
    python3 run.py --input "docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3/CSA236 Pharmacology/Basic principles revision.note"

    # Dry run (no writes, no ChromaDB — just test extraction + cleaning)
    python3 run.py --input "../..." --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from pipeline import process_note
from chunker import get_collection


def main():
    parser = argparse.ArgumentParser(description='Notability .note → RAG pipeline')
    parser.add_argument('--input', required=True, help='Path to .note file or directory')
    parser.add_argument('--output', default='./output', help='Output directory for .md files')
    parser.add_argument('--chroma', default='./chroma_db', help='ChromaDB persistence directory')
    parser.add_argument('--dry-run', action='store_true', help='Extract and clean only, no writes')
    parser.add_argument('--limit', type=int, default=None, help='Process at most N files (for testing)')
    args = parser.parse_args()

    input_path = Path(args.input)
    results = []
    errors = []

    if input_path.is_file() and input_path.suffix == '.note':
        note_files = [input_path]
    elif input_path.is_dir():
        note_files = sorted(input_path.rglob('*.note'))
    else:
        print(f"Error: {args.input} is not a .note file or directory.")
        sys.exit(1)

    if args.limit:
        note_files = note_files[:args.limit]

    total = len(note_files)
    print(f"Found {total} note(s) to process.\n")

    collection = None if args.dry_run else get_collection(args.chroma)

    for i, note_path in enumerate(note_files, 1):
        print(f"[{i}/{total}] {note_path.name}")
        try:
            result = process_note(
                str(note_path),
                args.output,
                args.chroma,
                collection,
                dry_run=args.dry_run,
            )
            results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            errors.append({'file': str(note_path), 'error': str(e)})
        print()

    # Summary
    print("=" * 60)
    print(f"Processed: {len(results)}/{total}")
    total_chunks = sum(r['chunk_count'] for r in results)
    total_flags = sum(len(r['review_flags']) for r in results)
    print(f"Total chunks ingested: {total_chunks}")
    print(f"Total [REVIEW_REQUIRED] flags: {total_flags}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  {e['file']}: {e['error']}")

    # Write results log
    if not args.dry_run:
        log_path = Path(args.output) / 'pipeline_results.json'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'w') as f:
            json.dump({'results': results, 'errors': errors}, f, indent=2)
        print(f"\nResults log: {log_path}")

    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
```

---

## `requirements.txt`

```
anthropic>=0.34.0
langchain-text-splitters>=0.3.0
chromadb>=0.5.0
```

---

## Build Order for the Agent

Execute these steps in order. Do not skip ahead. Mark each complete before starting the next.

**Step 1 — Setup**
1. Verify the `src/python/pipeline/` directory exists with `clinical_dictionary.py` and `cleaning_prompt.md`.
2. Write `requirements.txt` if not present.
3. Run `pip3 install -r requirements.txt`.
4. Verify `ANTHROPIC_API_KEY` is set.

**Step 2 — Write source files**

Write files in this order (each depends on the previous):
1. `src/python/pipeline/clinical_dictionary.py` (already exists)
2. `src/python/pipeline/extractor.py`
3. `src/python/pipeline/cleaning_agent.py`
4. `src/python/pipeline/structurer.py`
5. `src/python/pipeline/chunker.py`
6. `src/python/pipeline/pipeline.py`
7. `src/python/pipeline/run.py`

**Step 3 — Test the extractor in isolation**

```bash
cd pipeline
python3 -c "
import sys; sys.path.insert(0, 'src')
from extractor import extract_note
r = extract_note('docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3/CSA236 Pharmacology/Basic principles revision.note')
print('Title:', r['title'])
print('Subject:', r['subject'])
print('Modified:', r['last_modified'])
print('Text preview:', r['raw_text'][:300])
"
```

If `raw_text` is empty: use Bash to inspect the zip contents:
```bash
python3 -c "import zipfile; z = zipfile.ZipFile('docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3/CSA236 Pharmacology/Basic principles revision.note'); print(z.namelist()[:10])"
```
Check that `HandwritingIndex/index.plist` appears in the listing. If the note root directory name contains spaces, confirm the path construction in `extract_note` handles it.

**Step 4 — Dry-run single file**

```bash
cd pipeline
python3 run.py \
  --input "docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3/CSA236 Pharmacology/Basic principles revision.note" \
  --dry-run
```

Expected output: Stage 1 title, Stage 2 flag count, Stage 4 "Dry run" message. No API errors.

**Step 5 — Full run on single file**

```bash
cd pipeline
python3 run.py \
  --input "docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3/CSA236 Pharmacology/Basic principles revision.note" \
  --output ./data/notes_md/raw \
  --chroma ./data/chroma_db
```

Check `pipeline/output/` for a `.md` file. Open it and verify:
- YAML front matter is present and valid.
- `# Title` header matches the note name.
- Text is cleaned (no obvious OCR artifacts like "Pharmace dynamics").
- `[REVIEW_REQUIRED: ...]` tags are present if any uncertain values exist.

**Step 6 — Full run on one subject folder**

```bash
cd pipeline
python3 run.py \
  --input "docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3/CSA236 Pharmacology" \
  --output ./data/notes_md/raw \
  --chroma ./data/chroma_db \
  --limit 3
```

Run `--limit 3` first to validate before processing the full folder. Check `pipeline_results.json` for errors.

**Step 7 — Full batch run**

```bash
cd pipeline
python3 run.py \
  --input "docs/notabilityNotes/noteDocs/drive-download-20260401T053212Z-1-001/Paramedics 2021 sem 3" \
  --output ./data/notes_md/raw \
  --chroma ./data/chroma_db
```

---

## Error Handling Reference

| Error | Likely Cause | Fix |
|---|---|---|
| `KeyError: 'pages'` in extractor | `HandwritingIndex/index.plist` not found or different zip path | Print `zf.namelist()` to inspect; update `note_root` detection |
| `plistlib` fails to parse metadata | `NSKeyedArchiver` UID resolution failed | Add print of `objects` array to find correct indices |
| `anthropic.APIError: 401` | `ANTHROPIC_API_KEY` not set or invalid | `export ANTHROPIC_API_KEY=...` |
| `anthropic.APIError: 529` (overloaded) | Claude API at capacity | Retry with exponential backoff; add `time.sleep(5)` between notes |
| ChromaDB `InvalidDimensionException` | Collection created with wrong embedding | Delete `chroma_db/` and restart |
| `chunk_count: 0` | `structured_md` empty after YAML header | Check that `cleaned` is non-empty; print `structured_md[:200]` |
| `.md` file has garbled title | Unsafe characters in note name | The `re.sub` in `write_markdown` handles this; check the regex |

---

## Extending the Pipeline

**Adding a new subject folder:** Add an entry to `SUBJECT_TO_CATEGORY` in `clinical_dictionary.py` and extend the relevant `CLINICAL_DICTIONARY` list.

**Adding a new category:** Add a key to `CLINICAL_DICTIONARY` and a mapping in `SUBJECT_TO_CATEGORY`. The cleaning agent will automatically use the new terms.

**Changing the LLM model:** In `cleaning_agent.py`, change `model="claude-opus-4-6"` to `"claude-sonnet-4-6"` for lower cost. Only do this after validating that Sonnet handles your specific OCR noise patterns acceptably — test on a pharmacology note with drug names first.

**Querying ChromaDB (for the study app):**
```python
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("paramedic_notes")

results = collection.query(
    query_texts=["adrenaline dose cardiac arrest"],
    n_results=5,
    where={"category": "Pharmacology"},  # optional filter
)
# results['documents'] — the matched chunks
# results['metadatas'] — source_file, last_modified, has_review_flag per chunk
```

Filter by `has_review_flag: True` in your study app UI to highlight uncertain content.
