# Phase 1: Notability Notes Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert 533 Notability `.note` files into clean, categorised, chunked markdown in a ChromaDB vector store.

**Architecture:** Three-stage pipeline — Python extracts raw OCR text from `.note` ZIP archives, Claude Code subagents clean the OCR errors and assign categories, then Python chunks and ingests into ChromaDB. No external API calls.

**Tech Stack:** Python 3.10+, plistlib (stdlib), zipfile (stdlib), PyYAML, langchain-text-splitters, ChromaDB, argparse

**Spec:** `docs/superpowers/specs/2026-04-01-phase1-notability-pipeline-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/python/pipeline/extractor.py` | Parse `.note` ZIP archives → raw markdown with YAML front matter |
| `src/python/pipeline/clinical_dictionary.py` | Static category mappings + clinical term lists |
| `src/python/pipeline/structurer.py` | Validate and normalise cleaned markdown front matter |
| `src/python/pipeline/chunker.py` | Split text + ingest into ChromaDB |
| `src/python/pipeline/run.py` | CLI entrypoint (extract, ingest, status commands) |
| `src/python/pipeline/cleaning_prompt.md` | Reusable Claude Code prompt template for OCR cleaning |
| `tests/pipeline/test_extractor.py` | Extractor tests |
| `tests/pipeline/test_clinical_dictionary.py` | Dictionary/mapping tests |
| `tests/pipeline/test_structurer.py` | Structurer tests |
| `tests/pipeline/test_chunker.py` | Chunker tests |
| `tests/pipeline/test_run.py` | CLI integration tests |
| `tests/pipeline/conftest.py` | Shared fixtures (sample .note builder, temp dirs) |

---

### Task 1: Project setup — add dependencies and test infrastructure

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/pipeline/__init__.py`
- Create: `tests/pipeline/conftest.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Add pyyaml to pyproject.toml and pytest to dev deps**

```toml
# In pyproject.toml [project] dependencies, add:
  "pyyaml",

# dev deps already has pytest and httpx — confirm
```

- [ ] **Step 2: Create test directories and conftest with sample .note builder**

`tests/__init__.py` — empty

`tests/pipeline/__init__.py` — empty

`tests/pipeline/conftest.py`:
```python
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
            objects = [
                "$null",
                {
                    "noteUUIDKey": plistlib.UID(6),
                    "noteSubjectKey": plistlib.UID(3),
                    "noteTitleKey": plistlib.UID(2),
                    "noteLastModifiedDateKey": plistlib.UID(4),
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
```

- [ ] **Step 3: Install deps and verify pytest runs**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && pip install -e ".[dev]"`
Then: `python -m pytest tests/ -v --co`
Expected: conftest collected, no errors

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml tests/
git commit -m "chore: add pyyaml dep and pipeline test infrastructure"
```

---

### Task 2: Clinical dictionary and category mapping

**Files:**
- Create: `src/python/pipeline/clinical_dictionary.py`
- Create: `tests/pipeline/test_clinical_dictionary.py`

- [ ] **Step 1: Write the failing tests**

`tests/pipeline/test_clinical_dictionary.py`:
```python
from pipeline.clinical_dictionary import (
    SUBJECT_TO_CATEGORY,
    CLINICAL_TERMS,
    CANONICAL_CATEGORIES,
    get_category,
    get_terms_for_category,
)


def test_canonical_categories_has_all_required():
    required = {
        "Clinical Guidelines",
        "Medication Guidelines",
        "Operational Guidelines",
        "Clinical Skills",
        "Pathophysiology",
        "Pharmacology",
        "ECGs",
        "General Paramedicine",
    }
    assert required == set(CANONICAL_CATEGORIES)


def test_known_folder_maps_to_category():
    assert get_category("CSA236 Pharmacology") == "Pharmacology"


def test_unknown_folder_defaults_to_general():
    assert get_category("Some Unknown Folder") == "General Paramedicine"


def test_variant_folders_map_same_category():
    cat1 = get_category("CNA308 Ethics and Law")
    cat2 = get_category("CNA308 Legal and Ethical")
    assert cat1 == cat2 == "Operational Guidelines"


def test_all_mapped_categories_are_canonical():
    for folder, cat in SUBJECT_TO_CATEGORY.items():
        assert cat in CANONICAL_CATEGORIES, f"{folder} maps to non-canonical '{cat}'"


def test_clinical_terms_keys_are_canonical():
    for cat in CLINICAL_TERMS:
        assert cat in CANONICAL_CATEGORIES, f"Term list key '{cat}' not canonical"


def test_get_terms_for_category_returns_list():
    terms = get_terms_for_category("Pharmacology")
    assert isinstance(terms, list)
    assert len(terms) > 0
    assert "adrenaline" in terms


def test_get_terms_for_unknown_category_returns_empty():
    assert get_terms_for_category("Nonexistent") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/pipeline/test_clinical_dictionary.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement clinical_dictionary.py**

`src/python/pipeline/clinical_dictionary.py`:
```python
"""Static clinical dictionary and category mappings.

Maps Notability subject folder names to canonical clinical categories,
and provides domain-specific term lists for OCR cleaning context.
"""

CANONICAL_CATEGORIES = [
    "Clinical Guidelines",
    "Medication Guidelines",
    "Operational Guidelines",
    "Clinical Skills",
    "Pathophysiology",
    "Pharmacology",
    "ECGs",
    "General Paramedicine",
]

# Maps every known Notability folder name to a canonical category.
# Built from os.listdir enumeration of the actual archive.
SUBJECT_TO_CATEGORY: dict[str, str] = {
    # Top-level folders
    "ACTAS": "Clinical Guidelines",
    "CAA Medical emergencies 1": "Clinical Guidelines",
    "CNA308 Legal and Ethical": "Operational Guidelines",
    "CSA236 Pharmacology": "Pharmacology",
    "General Paramedicine": "General Paramedicine",
    # Sem 1 2021
    "CAA107 Principles of Paramedic Practice": "Clinical Skills",
    "CAA209 Evidence Based Research Methods": "General Paramedicine",
    "CAA210 Mental Health Care in Out of Hospital Practice": "Clinical Guidelines",
    "CNA151 Health and Health Care in Australia": "General Paramedicine",
    "Orientation": "General Paramedicine",
    # Sem 2 2021
    "CAA108 paramedic practice 2": "Clinical Skills",
    "CNA146 Aging": "General Paramedicine",
    "CNA156 Aboriginal": "General Paramedicine",
    "CNA157 Diversity": "General Paramedicine",
    "CXA107 intro to bioscience": "Pathophysiology",
    # Sem 3 2021
    "CAA109 placement": "Clinical Skills",
    "CAA205 Med Emergencies": "Clinical Guidelines",
    "CNA308 Ethics and Law": "Operational Guidelines",
    # Sem 1 2022
    "Arts and Dementia": "General Paramedicine",
    "CAA206 Med Emerg 2": "Clinical Guidelines",
    "CXA206 Bio 1": "Pathophysiology",
    # Sem 2 2022
    "CAA306 Trauma": "Clinical Guidelines",
    "CXA309 Health Services": "General Paramedicine",
    "CXA310 Bio 2": "Pathophysiology",
    # Sem 3 2022
    "CAA305 Environmental Emrgencies": "Clinical Guidelines",
    "CAA307 Obstetrics and Paediatrics": "Clinical Guidelines",
    "CAA309 Professional development": "Operational Guidelines",
}

DEFAULT_CATEGORY = "General Paramedicine"

CLINICAL_TERMS: dict[str, list[str]] = {
    "Pharmacology": [
        "adrenaline", "amiodarone", "midazolam", "ondansetron", "fentanyl",
        "morphine", "paracetamol", "ibuprofen", "salbutamol", "ipratropium",
        "ketamine", "methoxyflurane", "tranexamic acid", "naloxone", "atropine",
        "glucagon", "dexamethasone", "hydrocortisone", "diazepam", "lorazepam",
        "metoclopramide", "glyceryl trinitrate", "aspirin", "enoxaparin",
        "clopidogrel", "tenecteplase", "heparin", "noradrenaline",
    ],
    "Clinical Guidelines": [
        "anaphylaxis", "cardiac arrest", "acute coronary syndrome",
        "stroke", "seizure", "sepsis", "asthma", "COPD", "pneumothorax",
        "pulmonary oedema", "hypoglycaemia", "hyperglycaemia",
        "supraventricular tachycardia", "ventricular tachycardia",
        "ventricular fibrillation", "bradycardia", "hypertension",
    ],
    "Clinical Skills": [
        "laryngoscopy", "intubation", "cannulation", "tourniquet",
        "defibrillation", "cardioversion", "chest decompression",
        "cricothyroidotomy", "splinting", "traction", "suction",
        "bag-valve-mask", "oropharyngeal airway", "nasopharyngeal airway",
        "supraglottic airway", "i-gel", "intraosseous",
    ],
    "Pathophysiology": [
        "haemorrhage", "hypovolaemia", "perfusion", "ventilation",
        "oxygenation", "haemoglobin", "erythrocyte", "leukocyte",
        "myocardium", "cerebral", "renal", "hepatic", "ischaemia",
        "infarction", "oedema", "inflammation", "coagulation",
    ],
    "ECGs": [
        "sinus rhythm", "atrial fibrillation", "atrial flutter",
        "ST elevation", "ST depression", "T wave inversion",
        "bundle branch block", "QRS complex", "PR interval",
        "QT interval", "P wave", "axis deviation",
    ],
    "Operational Guidelines": [
        "triage", "clinical handover", "ISBAR", "documentation",
        "scope of practice", "duty of care", "consent", "capacity",
        "mandatory reporting", "clinical governance",
    ],
    "Medication Guidelines": [
        "indication", "contraindication", "dose", "route",
        "adverse effect", "interaction", "pharmacokinetics",
        "pharmacodynamics", "therapeutic index", "half-life",
    ],
}


def get_category(folder_name: str) -> str:
    """Return the canonical category for a Notability folder name."""
    return SUBJECT_TO_CATEGORY.get(folder_name.strip(), DEFAULT_CATEGORY)


def get_terms_for_category(category: str) -> list[str]:
    """Return clinical terms list for a category, or empty list if unknown."""
    return CLINICAL_TERMS.get(category, [])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_clinical_dictionary.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/clinical_dictionary.py tests/pipeline/test_clinical_dictionary.py
git commit -m "feat: add clinical dictionary and category mappings"
```

---

### Task 3: Extractor — parse .note archives to raw markdown

**Files:**
- Create: `src/python/pipeline/extractor.py`
- Create: `tests/pipeline/test_extractor.py`

- [ ] **Step 1: Write the failing tests**

`tests/pipeline/test_extractor.py`:
```python
import json
import yaml
from pathlib import Path

from pipeline.extractor import extract_note, extract_all


def test_extract_note_basic(build_note, tmp_output):
    """Extracts a simple .note with one page of OCR text."""
    note_path = build_note(
        title="Week 2",
        subject="CSA236 Pharmacology",
        pages={"1": "Adrenaline is used in cardiac arrest."},
    )
    result = extract_note(note_path, tmp_output["raw"])

    assert result["success"] is True
    assert result["title"] == "Week 2"
    assert result["subject"] == "CSA236 Pharmacology"

    # Check output file exists and has correct front matter
    out_file = tmp_output["raw"] / "CSA236 Pharmacology" / "Week 2.md"
    assert out_file.exists()
    content = out_file.read_text()
    # Parse YAML front matter
    parts = content.split("---\n", 2)
    meta = yaml.safe_load(parts[1])
    assert meta["title"] == "Week 2"
    assert meta["default_category"] == "Pharmacology"
    assert meta["source_file"] == "CSA236 Pharmacology/Week 2.note"
    assert "Adrenaline is used in cardiac arrest." in parts[2]


def test_extract_note_multi_page_ordered(build_note, tmp_output):
    """Pages are concatenated in numeric order regardless of dict ordering."""
    note_path = build_note(
        title="Multi",
        subject="Test",
        pages={"3": "page three", "1": "page one", "2": "page two"},
    )
    result = extract_note(note_path, tmp_output["raw"])
    out_file = tmp_output["raw"] / "Test" / "Multi.md"
    content = out_file.read_text()
    body = content.split("---\n", 2)[2]
    assert body.index("page one") < body.index("page two") < body.index("page three")


def test_extract_note_missing_handwriting(build_note, tmp_output):
    """Notes without HandwritingIndex are skipped with a warning."""
    note_path = build_note(
        title="PDF Only",
        subject="Test",
        include_handwriting=False,
    )
    result = extract_note(note_path, tmp_output["raw"])
    assert result["success"] is False
    assert "HandwritingIndex" in result["error"]
    out_file = tmp_output["raw"] / "Test" / "PDF Only.md"
    assert not out_file.exists()


def test_extract_note_nsdate_conversion(build_note, tmp_output):
    """NSDate epoch is correctly converted to ISO datetime."""
    # 652000000 NSDate = 652000000 + 978307200 = 1630307200 Unix
    # = 2021-08-30T04:26:40 UTC
    note_path = build_note(
        title="Dated",
        subject="Test",
        last_modified=652000000.0,
    )
    result = extract_note(note_path, tmp_output["raw"])
    out_file = tmp_output["raw"] / "Test" / "Dated.md"
    content = out_file.read_text()
    meta = yaml.safe_load(content.split("---\n", 2)[1])
    assert meta["last_modified"].startswith("2021-08-30")


def test_extract_all_processes_directory(build_note, tmp_output):
    """extract_all processes all .note files in a directory tree."""
    build_note(title="Note1", subject="SubjectA", pages={"1": "text a"})
    build_note(title="Note2", subject="SubjectB", pages={"1": "text b"})
    build_note(title="Bad", subject="SubjectC", include_handwriting=False)

    results = extract_all(tmp_output["base"].parent, tmp_output["raw"])
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    assert len(successes) == 2
    assert len(failures) == 1


def test_extract_all_writes_log(build_note, tmp_output):
    """extract_all writes extraction_log.json to parent of raw dir."""
    build_note(title="Bad", subject="Test", include_handwriting=False)
    extract_all(tmp_output["base"].parent, tmp_output["raw"])

    log_path = tmp_output["raw"].parent / "extraction_log.json"
    assert log_path.exists()
    log = json.loads(log_path.read_text())
    assert len(log["failures"]) == 1
    assert "HandwritingIndex" in log["failures"][0]["error"]
    assert "timestamp" in log["failures"][0]


def test_extract_all_limit(build_note, tmp_output):
    """--limit flag restricts number of files processed."""
    for i in range(5):
        build_note(title=f"Note{i}", subject="Batch", pages={"1": f"text {i}"})

    results = extract_all(tmp_output["base"].parent, tmp_output["raw"], limit=3)
    assert len(results) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/pipeline/test_extractor.py -v`
Expected: FAIL — `extract_note` not found

- [ ] **Step 3: Implement extractor.py**

`src/python/pipeline/extractor.py`:
```python
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
    for key, val in root_obj.items():
        if isinstance(val, plistlib.UID):
            resolved = objects[val.data]
            if key == "noteTitleKey":
                title = resolved
            elif key == "noteSubjectKey":
                subject = resolved
            elif key == "noteLastModifiedDateKey":
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_extractor.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/extractor.py tests/pipeline/test_extractor.py
git commit -m "feat: add .note extractor with OCR text and metadata parsing"
```

---

### Task 4: Structurer — validate and normalise cleaned markdown

**Files:**
- Create: `src/python/pipeline/structurer.py`
- Create: `tests/pipeline/test_structurer.py`

- [ ] **Step 1: Write the failing tests**

`tests/pipeline/test_structurer.py`:
```python
import yaml
from pathlib import Path

from pipeline.structurer import validate_and_normalise


def _write_cleaned_md(path: Path, front_matter: dict, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    path.write_text(f"---\n{fm}---\n{body}\n")
    return path


def test_valid_file_passes(tmp_path):
    """A file with all required front matter fields passes validation."""
    fm = {
        "title": "Week 2",
        "subject": "CSA236 Pharmacology",
        "categories": ["Pharmacology"],
        "source_file": "CSA236 Pharmacology/Week 2.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": [],
    }
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "Some cleaned text.")
    result = validate_and_normalise(md_path)
    assert result["valid"] is True


def test_missing_categories_fails(tmp_path):
    """A file missing 'categories' fails validation."""
    fm = {
        "title": "Week 2",
        "subject": "CSA236 Pharmacology",
        "source_file": "CSA236 Pharmacology/Week 2.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
    }
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "text")
    result = validate_and_normalise(md_path)
    assert result["valid"] is False
    assert "categories" in result["error"]


def test_normalises_whitespace(tmp_path):
    """Excessive blank lines in body are collapsed to double newlines."""
    fm = {
        "title": "Test",
        "subject": "Test",
        "categories": ["General Paramedicine"],
        "source_file": "Test/Test.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": [],
    }
    body = "Line one.\n\n\n\n\nLine two.\n\n\nLine three."
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, body)
    result = validate_and_normalise(md_path)
    assert result["valid"] is True
    content = md_path.read_text()
    body_part = content.split("---\n", 2)[2]
    assert "\n\n\n" not in body_part
    assert "Line one.\n\nLine two.\n\nLine three." in body_part


def test_returns_metadata(tmp_path):
    """Result includes parsed metadata for downstream use."""
    fm = {
        "title": "Week 2",
        "subject": "CSA236 Pharmacology",
        "categories": ["Pharmacology", "Clinical Skills"],
        "source_file": "CSA236 Pharmacology/Week 2.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": ["mldazolam → midazolam"],
    }
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "text")
    result = validate_and_normalise(md_path)
    assert result["categories"] == ["Pharmacology", "Clinical Skills"]
    assert result["has_review_flag"] is True
    assert result["source_file"] == "CSA236 Pharmacology/Week 2.note"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/pipeline/test_structurer.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement structurer.py**

`src/python/pipeline/structurer.py`:
```python
"""Validate and normalise cleaned markdown files before chunking.

Checks that YAML front matter has all required fields and normalises
body whitespace. Does not modify semantic content.
"""

import re
from pathlib import Path

import yaml

REQUIRED_FIELDS = ["title", "subject", "categories", "source_file", "last_modified", "review_flags"]


def validate_and_normalise(md_path: Path) -> dict:
    """Validate front matter and normalise body of a cleaned .md file.

    Returns a dict with validation result and parsed metadata.
    Writes the normalised file back in-place if valid.
    """
    content = md_path.read_text()

    # Split front matter from body
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {"valid": False, "error": "No YAML front matter found", "file": str(md_path)}

    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return {"valid": False, "error": f"Invalid YAML: {e}", "file": str(md_path)}

    if not isinstance(meta, dict):
        return {"valid": False, "error": "Front matter is not a dict", "file": str(md_path)}

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in meta:
            return {"valid": False, "error": f"Missing field: {field}", "file": str(md_path)}

    # Normalise body — collapse 3+ newlines to 2
    body = parts[2]
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.strip() + "\n"

    # Write back normalised version
    fm_str = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
    md_path.write_text(f"---\n{fm_str}---\n{body}")

    review_flags = meta.get("review_flags", [])
    return {
        "valid": True,
        "file": str(md_path),
        "title": meta["title"],
        "source_file": meta["source_file"],
        "categories": meta["categories"],
        "last_modified": meta["last_modified"],
        "has_review_flag": bool(review_flags),
        "review_flags": review_flags,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_structurer.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/structurer.py tests/pipeline/test_structurer.py
git commit -m "feat: add structurer for cleaned markdown validation"
```

---

### Task 5: Chunker — split text and ingest into ChromaDB

**Files:**
- Create: `src/python/pipeline/chunker.py`
- Create: `tests/pipeline/test_chunker.py`

- [ ] **Step 1: Write the failing tests**

`tests/pipeline/test_chunker.py`:
```python
import yaml
from pathlib import Path

import chromadb

from pipeline.chunker import chunk_and_ingest, sanitise_id


def _write_cleaned_md(path: Path, front_matter: dict, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    path.write_text(f"---\n{fm}---\n{body}\n")
    return path


def _make_fm(source_file="Test/Note.note", categories=None):
    return {
        "title": "Note",
        "subject": "Test",
        "categories": categories or ["General Paramedicine"],
        "source_file": source_file,
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": [],
    }


def test_sanitise_id():
    assert sanitise_id("CSA236 Pharmacology/Week 2.note") == "CSA236_Pharmacology__Week_2.note"


def test_chunk_and_ingest_basic(tmp_path):
    """A short note produces at least one chunk in ChromaDB."""
    md_path = _write_cleaned_md(
        tmp_path / "test.md",
        _make_fm(),
        "This is a short piece of text for testing the chunker.",
    )
    db_path = tmp_path / "chroma"
    result = chunk_and_ingest(md_path, db_path)

    assert result["success"] is True
    assert result["chunk_count"] >= 1

    # Verify in ChromaDB
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("paramedic_notes")
    assert collection.count() >= 1


def test_chunk_metadata_correct(tmp_path):
    """Chunk metadata includes all required fields."""
    md_path = _write_cleaned_md(
        tmp_path / "test.md",
        _make_fm(
            source_file="CSA236 Pharmacology/Week 2.note",
            categories=["Pharmacology", "Clinical Skills"],
        ),
        "Some clinical content about pharmacology and skills.",
    )
    db_path = tmp_path / "chroma"
    chunk_and_ingest(md_path, db_path)

    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("paramedic_notes")
    result = collection.get(include=["metadatas"])
    meta = result["metadatas"][0]

    assert meta["source_type"] == "notability_note"
    assert meta["source_file"] == "CSA236 Pharmacology/Week 2.note"
    assert meta["categories"] == "Pharmacology,Clinical Skills"
    assert meta["chunk_index"] == 0
    assert meta["has_review_flag"] is False


def test_reingest_is_idempotent(tmp_path):
    """Ingesting the same file twice does not duplicate chunks."""
    md_path = _write_cleaned_md(
        tmp_path / "test.md",
        _make_fm(),
        "Text for idempotency test.",
    )
    db_path = tmp_path / "chroma"
    chunk_and_ingest(md_path, db_path)
    count1 = chromadb.PersistentClient(path=str(db_path)).get_collection("paramedic_notes").count()

    chunk_and_ingest(md_path, db_path)
    count2 = chromadb.PersistentClient(path=str(db_path)).get_collection("paramedic_notes").count()

    assert count1 == count2


def test_long_text_produces_multiple_chunks(tmp_path):
    """Text longer than 800 chars is split into multiple chunks."""
    long_text = "This is a paragraph about clinical practice. " * 50  # ~2300 chars
    md_path = _write_cleaned_md(tmp_path / "test.md", _make_fm(), long_text)
    db_path = tmp_path / "chroma"
    result = chunk_and_ingest(md_path, db_path)
    assert result["chunk_count"] > 1


def test_review_flag_metadata(tmp_path):
    """has_review_flag is True when review_flags are present."""
    fm = _make_fm()
    fm["review_flags"] = ["mldazolam → midazolam"]
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "Some text.")
    db_path = tmp_path / "chroma"
    chunk_and_ingest(md_path, db_path)

    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("paramedic_notes")
    meta = collection.get(include=["metadatas"])["metadatas"][0]
    assert meta["has_review_flag"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/pipeline/test_chunker.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement chunker.py**

`src/python/pipeline/chunker.py`:
```python
"""Chunk cleaned markdown and ingest into ChromaDB.

Uses RecursiveCharacterTextSplitter (800 chars, 100 overlap) and
ChromaDB PersistentClient with collection 'paramedic_notes'.
"""

import re
from pathlib import Path

import chromadb
import yaml
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
COLLECTION_NAME = "paramedic_notes"

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def sanitise_id(source_file: str) -> str:
    """Convert source_file path to a safe ChromaDB ID prefix."""
    return source_file.replace("/", "__").replace(" ", "_")


def chunk_and_ingest(md_path: Path, db_path: Path) -> dict:
    """Chunk a single cleaned .md file and ingest into ChromaDB.

    Deletes any existing chunks for this source_file before inserting
    (idempotent re-ingestion).

    Returns a result dict with chunk count and metadata.
    """
    content = md_path.read_text()
    parts = content.split("---\n", 2)
    meta = yaml.safe_load(parts[1])
    body = parts[2].strip()

    source_file = meta["source_file"]
    categories = meta.get("categories", [])
    review_flags = meta.get("review_flags", [])
    last_modified = meta.get("last_modified", "")

    # Chunk the body text
    chunks = _splitter.split_text(body)
    if not chunks:
        return {
            "success": True,
            "source_file": source_file,
            "chunk_count": 0,
        }

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Delete existing chunks for this source file (idempotent re-ingestion)
    id_prefix = sanitise_id(source_file)
    existing = collection.get(where={"source_file": source_file})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    # Prepare chunk data
    ids = [f"{id_prefix}_chunk_{i:04d}" for i in range(len(chunks))]
    metadatas = [
        {
            "source_type": "notability_note",
            "source_file": source_file,
            "categories": ",".join(categories),
            "chunk_index": i,
            "last_modified": last_modified,
            "has_review_flag": bool(review_flags),
        }
        for i in range(len(chunks))
    ]

    collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    return {
        "success": True,
        "source_file": source_file,
        "chunk_count": len(chunks),
        "categories": categories,
        "has_review_flag": bool(review_flags),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_chunker.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/chunker.py tests/pipeline/test_chunker.py
git commit -m "feat: add chunker with ChromaDB ingestion"
```

---

### Task 6: CLI entrypoint — extract, ingest, status commands

**Files:**
- Create: `src/python/pipeline/run.py`
- Create: `tests/pipeline/test_run.py`

- [ ] **Step 1: Write the failing tests**

`tests/pipeline/test_run.py`:
```python
import json
import subprocess
import sys
import yaml
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "src" / "python" / "pipeline"
RUN_SCRIPT = PIPELINE_DIR / "run.py"


def _run_cli(*args, cwd=None):
    """Run the pipeline CLI and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(RUN_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd or str(PIPELINE_DIR.parents[1]),  # src/python
    )
    return result.returncode, result.stdout, result.stderr


def _write_cleaned_md(path: Path, title="Note", subject="Test"):
    fm = {
        "title": title,
        "subject": subject,
        "categories": ["General Paramedicine"],
        "source_file": f"{subject}/{title}.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
    path.write_text(f"---\n{fm_str}---\nSome cleaned text for testing.\n")


def test_status_command(tmp_path, build_note):
    """status command reports counts correctly."""
    raw_dir = tmp_path / "raw"
    cleaned_dir = tmp_path / "cleaned"
    raw_dir.mkdir()
    cleaned_dir.mkdir()

    # Create 2 raw files
    for i in range(2):
        (raw_dir / f"note{i}.md").write_text("raw")
    # Create 1 cleaned file
    _write_cleaned_md(cleaned_dir / "note0.md")

    code, stdout, _ = _run_cli(
        "status",
        "--raw-dir", str(raw_dir),
        "--cleaned-dir", str(cleaned_dir),
        "--db-path", str(tmp_path / "chroma"),
    )
    assert code == 0
    assert "2" in stdout  # raw count
    assert "1" in stdout  # cleaned count
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/pipeline/test_run.py -v`
Expected: FAIL — run.py does not exist or has no commands

- [ ] **Step 3: Implement run.py**

`src/python/pipeline/run.py`:
```python
"""CLI entrypoint for the Notability notes pipeline.

Commands:
    extract [--limit N]                     Extract .note files to raw markdown
    ingest [--dry-run]                      Chunk and ingest cleaned files to ChromaDB
    status                                  Report pipeline state

All paths default to the project's standard locations but can be overridden
with flags for testing.
"""

import argparse
import json
import sys
from pathlib import Path

# Resolve project root (StudyBot/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_SOURCE_DIR = PROJECT_ROOT / "docs" / "notabilityNotes" / "noteDocs"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "notes_md" / "raw"
DEFAULT_CLEANED_DIR = PROJECT_ROOT / "data" / "notes_md" / "cleaned"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "chroma_db"


def cmd_extract(args):
    from pipeline.extractor import extract_all

    source_dir = Path(args.source_dir)
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    results = extract_all(source_dir, raw_dir, limit=args.limit)
    successes = sum(1 for r in results if r["success"])
    failures = sum(1 for r in results if not r["success"])
    print(f"\nDone. {successes} extracted, {failures} failed.")
    if failures:
        print(f"See {raw_dir / 'extraction_log.json'} for failure details.")


def cmd_ingest(args):
    from pipeline.structurer import validate_and_normalise
    from pipeline.chunker import chunk_and_ingest

    cleaned_dir = Path(args.cleaned_dir)
    db_path = Path(args.db_path)

    md_files = sorted(cleaned_dir.rglob("*.md"))
    if not md_files:
        print(f"No cleaned .md files found in {cleaned_dir}")
        return

    results = []
    for md_path in md_files:
        # Validate first
        val = validate_and_normalise(md_path)
        if not val["valid"]:
            print(f"  SKIP (invalid): {md_path.name} — {val['error']}")
            results.append({"source_file": str(md_path), "success": False, "error": val["error"]})
            continue

        if args.dry_run:
            print(f"  DRY RUN: {val['source_file']} — valid, {len(val['categories'])} categories")
            results.append({"source_file": val["source_file"], "success": True, "chunk_count": 0, "dry_run": True})
            continue

        # Chunk and ingest
        result = chunk_and_ingest(md_path, db_path)
        print(f"  OK: {result['source_file']} — {result['chunk_count']} chunks")
        results.append(result)

    # Write ingestion log to parent of cleaned/ (i.e. data/notes_md/)
    log_path = cleaned_dir.parent / "ingestion_log.json"
    log_path.write_text(json.dumps(results, indent=2, default=str))

    total = len(results)
    ok = sum(1 for r in results if r.get("success"))
    total_chunks = sum(r.get("chunk_count", 0) for r in results)
    flagged = sum(1 for r in results if r.get("has_review_flag"))

    # Category distribution
    cat_counts: dict[str, int] = {}
    for r in results:
        for cat in r.get("categories", []):
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    print(f"\nIngested {ok}/{total} files, {total_chunks} total chunks, {flagged} with review flags.")
    if cat_counts:
        print("Category distribution:")
        for cat, count in sorted(cat_counts.items()):
            print(f"  {cat}: {count}")


def cmd_status(args):
    raw_dir = Path(args.raw_dir)
    cleaned_dir = Path(args.cleaned_dir)
    db_path = Path(args.db_path)

    raw_count = len(list(raw_dir.rglob("*.md"))) if raw_dir.exists() else 0
    cleaned_count = len(list(cleaned_dir.rglob("*.md"))) if cleaned_dir.exists() else 0
    pending = raw_count - cleaned_count

    # Check extraction failures (log is at data/notes_md/ level)
    log_path = raw_dir.parent / "extraction_log.json"
    extraction_failures = 0
    if log_path.exists():
        log = json.loads(log_path.read_text())
        extraction_failures = log.get("failed", 0)

    # Check ChromaDB
    ingested = 0
    if db_path.exists():
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(db_path))
            collection = client.get_collection("paramedic_notes")
            ingested = collection.count()
        except Exception:
            pass

    print(f"Raw extracted:       {raw_count}")
    print(f"Extraction failures: {extraction_failures}")
    print(f"Cleaned:             {cleaned_count}")
    print(f"Pending cleaning:    {pending}")
    print(f"ChromaDB chunks:     {ingested}")


def main():
    parser = argparse.ArgumentParser(description="Notability notes pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    # extract
    p_extract = sub.add_parser("extract", help="Extract .note files to raw markdown")
    p_extract.add_argument("--limit", type=int, default=None, help="Max files to process")
    p_extract.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    p_extract.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))

    # ingest
    p_ingest = sub.add_parser("ingest", help="Chunk and ingest cleaned files to ChromaDB")
    p_ingest.add_argument("--dry-run", action="store_true", help="Validate without writing to ChromaDB")
    p_ingest.add_argument("--cleaned-dir", default=str(DEFAULT_CLEANED_DIR))
    p_ingest.add_argument("--db-path", default=str(DEFAULT_DB_PATH))

    # status
    p_status = sub.add_parser("status", help="Report pipeline state")
    p_status.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    p_status.add_argument("--cleaned-dir", default=str(DEFAULT_CLEANED_DIR))
    p_status.add_argument("--db-path", default=str(DEFAULT_DB_PATH))

    args = parser.parse_args()
    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_run.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/pipeline/run.py tests/pipeline/test_run.py
git commit -m "feat: add pipeline CLI with extract, ingest, status commands"
```

---

### Task 7: Cleaning prompt template

**Files:**
- Create: `src/python/pipeline/cleaning_prompt.md`

- [ ] **Step 1: Write the cleaning prompt template**

`src/python/pipeline/cleaning_prompt.md`:
```markdown
# OCR Cleaning Instructions

You are cleaning OCR-extracted handwritten notes from a paramedic student's Notability app. Follow these instructions precisely.

## Setup

1. Read `src/python/pipeline/clinical_dictionary.py` for the clinical term lists and category mappings.
2. Glob `data/notes_md/raw/**/*.md` to find all raw extracted files.
3. Glob `data/notes_md/cleaned/**/*.md` to find already-cleaned files.
4. Skip any raw file that already has a corresponding cleaned file at the same relative path under `data/notes_md/cleaned/`.

## Cleaning Rules

For each raw file:

1. **Read the file** — it has YAML front matter (title, subject, default_category, source_file, last_modified) followed by raw OCR text.

2. **Fix OCR errors only.** Common patterns:
   - Character substitutions: `8` for `g`, `1` for `l`, `rn` for `m`, `0` for `O`
   - Broken words: `mid azolam` → `midazolam`
   - Garbled drug names: `arniodarone` → `amiodarone`
   - Missing spaces: `cardiacarrest` → `cardiac arrest`
   - **Never** rephrase, reword, reorganise, add content, or remove content
   - **Never** correct factual or clinical errors — only fix OCR artefacts

3. **Flag uncertain corrections** with `[REVIEW_REQUIRED: <original> → <correction>]` inline. Use this when you're not confident the OCR error is what you think it is — especially for drug names and dosages.

4. **Assign 1–3 categories** based on the note's actual content (not just the folder name). Choose from:
   - Clinical Guidelines
   - Medication Guidelines
   - Operational Guidelines
   - Clinical Skills
   - Pathophysiology
   - Pharmacology
   - ECGs
   - General Paramedicine

5. **Write the cleaned file** to `data/notes_md/cleaned/` at the same relative path. Use this YAML front matter format:

```yaml
---
title: "<from raw file>"
subject: "<from raw file>"
categories:
  - "<primary category>"
  - "<secondary if applicable>"
source_file: "<from raw file>"
last_modified: "<from raw file>"
review_flags:
  - "<original> → <correction>"
---

<cleaned text>
```

If no review flags, use `review_flags: []`.

## Batching

Process files in batches of 5–10 using parallel subagents, grouped by folder. Each subagent should be given:
- The list of raw file paths to clean
- The relevant clinical terms for the folder's default category
- These cleaning rules

## After Cleaning

Print a summary: how many files were cleaned, how many skipped (already done), how many review flags were generated.
```

- [ ] **Step 2: Commit**

```bash
git add src/python/pipeline/cleaning_prompt.md
git commit -m "feat: add Claude Code cleaning prompt template"
```

---

### Task 8: Integration test — full extract → ingest flow

**Files:**
- Create: `tests/pipeline/test_integration.py`

- [ ] **Step 1: Write integration test**

`tests/pipeline/test_integration.py`:
```python
"""End-to-end integration test: extract → (simulate clean) → ingest."""

import yaml
import chromadb
from pathlib import Path

from pipeline.extractor import extract_all
from pipeline.structurer import validate_and_normalise
from pipeline.chunker import chunk_and_ingest


def _simulate_cleaning(raw_dir: Path, cleaned_dir: Path):
    """Simulate Claude Code cleaning by copying raw files with updated front matter."""
    for raw_file in raw_dir.rglob("*.md"):
        content = raw_file.read_text()
        parts = content.split("---\n", 2)
        meta = yaml.safe_load(parts[1])

        # Simulate: promote default_category to categories list, add review_flags
        cleaned_meta = {
            "title": meta["title"],
            "subject": meta["subject"],
            "categories": [meta.get("default_category", "General Paramedicine")],
            "source_file": meta["source_file"],
            "last_modified": meta["last_modified"],
            "review_flags": [],
        }

        rel_path = raw_file.relative_to(raw_dir)
        out_path = cleaned_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fm_str = yaml.dump(cleaned_meta, default_flow_style=False, allow_unicode=True)
        out_path.write_text(f"---\n{fm_str}---\n{parts[2]}")


def test_full_pipeline(build_note, tmp_output):
    """Extract → simulate clean → validate → ingest → query ChromaDB."""
    # Create test notes
    build_note(
        title="Adrenaline",
        subject="CSA236 Pharmacology",
        pages={"1": "Adrenaline 1mg IV for cardiac arrest", "2": "Repeat every 3-5 minutes"},
    )
    build_note(
        title="Triage",
        subject="General Paramedicine",
        pages={"1": "Triage categories: immediate, urgent, delayed, dead"},
    )

    # Extract
    source_dir = tmp_output["base"].parent
    raw_dir = tmp_output["raw"]
    results = extract_all(source_dir, raw_dir)
    assert sum(1 for r in results if r["success"]) == 2

    # Simulate cleaning
    cleaned_dir = tmp_output["cleaned"]
    _simulate_cleaning(raw_dir, cleaned_dir)

    # Validate and ingest
    db_path = tmp_output["base"] / "chroma"
    for md_path in cleaned_dir.rglob("*.md"):
        val = validate_and_normalise(md_path)
        assert val["valid"], f"Validation failed: {val.get('error')}"
        result = chunk_and_ingest(md_path, db_path)
        assert result["success"]

    # Query ChromaDB
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("paramedic_notes")
    assert collection.count() >= 2

    # Search for adrenaline content
    results = collection.query(query_texts=["adrenaline cardiac arrest"], n_results=1)
    assert len(results["documents"][0]) == 1
    assert "Adrenaline" in results["documents"][0][0] or "adrenaline" in results["documents"][0][0].lower()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/pipeline/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_integration.py
git commit -m "test: add end-to-end pipeline integration test"
```

---

### Task 9: Run extraction on real data (pilot)

**No new files — operational task.**

- [ ] **Step 1: Run extraction with --limit 20**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python src/python/pipeline/run.py extract --limit 20`
Expected: "Extracted N/20 notes (M failures)" — verify output files appear in `data/notes_md/raw/`

- [ ] **Step 2: Inspect a few extracted files**

Check 2–3 output `.md` files in `data/notes_md/raw/` to confirm:
- YAML front matter is correct (title, subject, category, source_file, last_modified)
- OCR text is present and readable (even if messy)
- No binary garbage or encoding issues

- [ ] **Step 3: Check extraction log for failures**

Run: `cat data/notes_md/extraction_log.json | python -m json.tool`
Review failures — confirm they're expected (e.g. PDF-only notes with no HandwritingIndex)

- [ ] **Step 4: Run status**

Run: `python src/python/pipeline/run.py status`
Expected: shows raw count = 20, cleaned = 0, pending = 20

- [ ] **Step 5: Commit extracted pilot data (optional — may gitignore data/)**

If data/ is gitignored, skip. Otherwise:
```bash
git add data/notes_md/raw/
git commit -m "data: extract pilot batch of 20 notability notes"
```

---

### Task 10: Claude Code cleaning — pilot batch

**No new code files — operational task using Claude Code.**

- [ ] **Step 1: Run Claude Code cleaning on pilot batch**

Start a new Claude Code session and say:
> "Follow the instructions in `src/python/pipeline/cleaning_prompt.md`. Only process the files in `data/notes_md/raw/`. This is a pilot batch of ~20 files."

- [ ] **Step 2: Review cleaned output quality**

Check 5–6 cleaned files in `data/notes_md/cleaned/`:
- OCR errors were fixed without altering meaning
- Categories assigned make sense for the content
- Review flags are used appropriately (not too many, not too few)
- Front matter format matches the spec

- [ ] **Step 3: Tune cleaning prompt if needed**

If quality issues are found, edit `src/python/pipeline/cleaning_prompt.md` and re-run on a few problem files.

- [ ] **Step 4: Run ingest on pilot cleaned files**

Run: `python src/python/pipeline/run.py ingest`
Expected: "Ingested N/N files, X total chunks, Y with review flags."

- [ ] **Step 5: Verify ChromaDB queries work**

Run:
```python
python3 -c "
import chromadb
client = chromadb.PersistentClient(path='data/chroma_db')
col = client.get_collection('paramedic_notes')
print(f'Total chunks: {col.count()}')
results = col.query(query_texts=['cardiac arrest'], n_results=3)
for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
    print(f'[{meta[\"source_file\"]}] {doc[:100]}...')
"
```
Expected: relevant chunks returned with correct metadata

- [ ] **Step 6: Run status to confirm**

Run: `python src/python/pipeline/run.py status`
Expected: raw ~20, cleaned ~20, ChromaDB chunks > 0

---

### Task 11: Full extraction and cleaning

**No new code files — operational task.**

- [ ] **Step 1: Extract all 533 notes**

Run: `python src/python/pipeline/run.py extract`
Expected: "Extracted N/533 notes (M failures)"

- [ ] **Step 2: Review extraction log**

Check `data/notes_md/extraction_log.json` — ensure failures are expected (no HandwritingIndex).

- [ ] **Step 3: Clean all files via Claude Code sessions**

Run multiple Claude Code sessions (one per folder group) using `src/python/pipeline/cleaning_prompt.md`. The prompt handles partial runs — it skips already-cleaned files.

- [ ] **Step 4: Run full ingestion**

Run: `python src/python/pipeline/run.py ingest`

- [ ] **Step 5: Final status check**

Run: `python src/python/pipeline/run.py status`
Expected: all files extracted, cleaned, and ingested. ChromaDB populated.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: complete Phase 1 — notability notes pipeline"
```

---

## Summary

| Task | What | Type |
|------|------|------|
| 1 | Dependencies + test infrastructure | Setup |
| 2 | Clinical dictionary + category mapping | Code + tests |
| 3 | Extractor (.note → raw .md) | Code + tests |
| 4 | Structurer (validation + normalisation) | Code + tests |
| 5 | Chunker (text splitting + ChromaDB) | Code + tests |
| 6 | CLI entrypoint (extract, ingest, status) | Code + tests |
| 7 | Cleaning prompt template | Docs |
| 8 | Integration test (full flow) | Tests |
| 9 | Pilot extraction (20 files) | Operational |
| 10 | Pilot cleaning + ingest + verify | Operational |
| 11 | Full extraction + cleaning + ingest | Operational |
