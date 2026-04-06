# Phase 1: Notability Notes Pipeline — Design Spec

**Date:** 2026-04-01
**Project:** Clinical Recall Assistant (StudyBot)
**Phase:** 1 — Data Pipeline: Notability Notes

---

## Overview

Convert 533 `.note` files (Notability exports) into clean, categorised, chunked markdown in a ChromaDB vector store. The pipeline uses Python for all mechanical work (ZIP parsing, plist reading, chunking, database ingestion) and Claude Code subagents for OCR cleaning — avoiding any external API cost.

### Architecture: Monolithic Python + Claude Code Cleaning Pass

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  python run.py      │     │  Claude Code session  │     │  python run.py      │
│  extract            │ ──▶ │  OCR cleaning agents  │ ──▶ │  ingest             │
│                     │     │                        │     │                     │
│  .note → raw .md    │     │  raw .md → cleaned .md │     │  cleaned .md →      │
│  data/notes_md/raw/ │     │  data/notes_md/cleaned/│     │  ChromaDB           │
└─────────────────────┘     └──────────────────────┘     └─────────────────────┘
```

---

## Section 1: Extraction (`python run.py extract`)

**Input:** 533 `.note` files under `docs/notabilityNotes/noteDocs/drive-download-.../`

**Process per file:**
1. Unzip the `.note` file (it's a ZIP archive)
2. Parse `metadata.plist` for title, subject (folder name), last modified date (NSDate epoch: add 978307200 to convert to Unix timestamp)
3. Parse `HandwritingIndex/index.plist` — concatenate `.text` fields from each page key, ordered by page number (1-indexed string keys)
4. Map the Notability subject folder to a default clinical category via `SUBJECT_TO_CATEGORY`

**Scope:** Phase 1 extracts OCR handwriting text only. Images (`Images/`), PDFs (`PDFs/`, `NBPDFIndex/`), and audio recordings inside `.note` archives are intentionally skipped. Notes with no `HandwritingIndex` (e.g. PDF-only notes) will be logged and skipped.

**Edge cases:**
- Missing `HandwritingIndex`: skip file with warning logged
- Empty pages: include as blank in concatenation (preserves page structure)
- Duplicate `Paramedics 2021 sem 1` folders (trailing space): strip whitespace when matching, deduplicate

**Output:** One raw `.md` file per note in `data/notes_md/raw/`, preserving folder hierarchy. Each file has YAML front matter:

```yaml
---
title: "Week 2"
subject: "CSA236 Pharmacology"
default_category: "Pharmacology"
source_file: "CSA236 Pharmacology/Week 2.note"
last_modified: "2021-08-15T10:30:00"
---

[raw OCR text follows]
```

**Error handling:** Per-file try/except — failures logged to `data/notes_md/extraction_log.json` (file path, error message, timestamp). Pipeline continues on failure.

**Source:** `src/python/pipeline/extractor.py`

---

## Section 2: Clinical Dictionary & Category Mapping

**Source:** `src/python/pipeline/clinical_dictionary.py`

A static Python module (no LLM calls) containing:

### `SUBJECT_TO_CATEGORY`

Maps Notability folder names to default clinical categories. Used to:
- Set a default category during extraction
- Determine which clinical dictionary terms to send to the cleaning agent

```python
# Examples only — the full dict MUST be built by enumerating all actual folder
# names from the archive at implementation time. There are ~20+ distinct subject
# folders across semester directories.
SUBJECT_TO_CATEGORY = {
    "CSA236 Pharmacology": "Pharmacology",
    "CAA205 Med Emergencies": "Clinical Guidelines",
    "CNA308 Ethics and Law": "Operational Guidelines",
    "CNA308 Legal and Ethical": "Operational Guidelines",  # variant name, same subject
    # ... etc for all ~20+ folders
}
```

Unmapped folders default to `"General Paramedicine"`.

**Variant handling:** The same subject may appear under different folder names across semesters (e.g. `CNA308 Ethics and Law` vs `CNA308 Legal and Ethical`). All variants must be mapped. The implementation should enumerate folders with `os.listdir`, then manually map each to a category.

**Note:** This spec supersedes category names in `Guides/PIPELINE_AGENT_GUIDE.md` (which uses `"General"` instead of `"General Paramedicine"`, etc.). The canonical list in Section 3 is authoritative.

**Note:** This is a *default* only. The Claude Code cleaning agents assign the final per-note categories based on content (see Section 3).

### `CLINICAL_TERMS`

Category-keyed lists of correct spellings for common paramedic terms. Provided as context to cleaning agents so they can recognise and correct domain-specific OCR errors:

```python
CLINICAL_TERMS = {
    "Pharmacology": ["adrenaline", "amiodarone", "midazolam", "ondansetron", ...],
    "Cardiac": ["ventricular fibrillation", "supraventricular tachycardia", ...],
    "Clinical Skills": ["laryngoscopy", "cannulation", "tourniquet", ...],
    # ... etc
}
```

Built incrementally — start with terms from the pipeline guide, extend as new terms appear during the pilot.

---

## Section 3: Claude Code OCR Cleaning Workflow

**When:** After extraction, before ingestion. Run as a Claude Code session.

**Operational workflow:**

The cleaning step is a manual Claude Code session — the user starts a Claude Code conversation and asks it to clean the extracted notes. Claude Code then:

1. Reads `src/python/pipeline/clinical_dictionary.py` to load the term lists
2. Globs `data/notes_md/raw/` to find files needing cleaning
3. Dispatches parallel subagents (via the Agent tool) in batches of ~5–10 files, grouped by folder
4. Each subagent reads its assigned raw `.md` files, cleans the OCR text, and writes cleaned `.md` files to the corresponding path under `data/notes_md/cleaned/`
5. A summary is printed when all batches complete

A reusable prompt template is stored at `src/python/pipeline/cleaning_prompt.md` so the user can kick off cleaning with: "Follow the instructions in `src/python/pipeline/cleaning_prompt.md`"

**Each subagent receives (via its prompt):**
- The raw OCR text (read from the file)
- Relevant clinical dictionary terms (based on the source folder's default category)
- Instructions: fix OCR errors only, never rephrase or add content
- Flag uncertain corrections with `[REVIEW_REQUIRED: <original> → <correction>]`
- Assign 1–3 categories from the canonical list based on actual content
- Write the cleaned `.md` file directly using the Write tool

### Canonical categories

- Clinical Guidelines
- Medication Guidelines
- Operational Guidelines
- Clinical Skills
- Pathophysiology
- Pharmacology
- ECGs
- General Paramedicine

### Subagent output per note

The subagent writes a cleaned `.md` file directly (not JSON). The output file mirrors the raw file but with cleaned text and updated front matter (see Output below).

### Output

Cleaned `.md` files written to `data/notes_md/cleaned/`, same folder hierarchy, with updated YAML front matter:

```yaml
---
title: "Week 2"
subject: "CSA236 Pharmacology"
categories:
  - Pharmacology
  - Clinical Skills
source_file: "CSA236 Pharmacology/Week 2.note"
last_modified: "2021-08-15T10:30:00"
review_flags:
  - "mldazolam → midazolam"
---

[cleaned text follows]
```

### Multi-category support

Notes can be tagged with up to 3 categories (primary + secondary). The folder-level `SUBJECT_TO_CATEGORY` determines which dictionary terms the agent receives as context; the agent assigns the final categories based on content.

### Pilot phase

First run: ~15–20 files from 3–4 different subject folders. User reviews output quality. Prompt tuned if needed, then batch the rest.

### Batching strategy

~5–10 files per subagent dispatch. Independent notes run fully in parallel. If a subagent fails on a file, it logs the failure and continues with the remaining files in its batch — successful files are kept.

### Session strategy

With 533 files at ~5–10 per batch, expect ~50–100 subagent dispatches. This should be split across multiple Claude Code sessions (e.g. one folder group per session) to stay within context limits. The cleaning prompt template handles partial runs — it skips files that already have a cleaned counterpart in `data/notes_md/cleaned/`.

---

## Section 4: Structuring & Ingestion (`python run.py ingest`)

**Input:** Cleaned `.md` files from `data/notes_md/cleaned/`

### Structurer (rules-based, no LLM)

- Reads each cleaned `.md` file
- Validates YAML front matter is intact (title, subject, categories, source_file, last_modified, review_flags)
- Normalises formatting — consistent heading levels, whitespace cleanup
- No file transformation — validation and normalisation only

### Chunker + ChromaDB ingestion

- **Splitter:** `RecursiveCharacterTextSplitter` from langchain — 800 chars, 100 overlap, splits on `\n\n` → `\n` → sentence → character
- **Database:** ChromaDB `PersistentClient` at `data/chroma_db/`, collection `"paramedic_notes"`, cosine distance
- **Chunk ID format:** `{sanitised_source_file}_chunk_{i:04d}` — source_file is sanitised (spaces → `_`, slashes → `__`) to produce safe IDs
- **Chunk metadata:**

```python
{
    "source_type": "notability_note",
    "source_file": "CSA236 Pharmacology/Week 2.note",
    "categories": "Pharmacology,Clinical Skills",  # comma-separated string
    "chunk_index": 3,
    "last_modified": "2021-08-15T10:30:00",
    "has_review_flag": True
}
```

### Reporting

Writes `data/notes_md/ingestion_log.json` — per-file summary (chunk count, categories, review flags). Prints a final summary: total files, total chunks, files with review flags, category distribution.

### Re-runnability

Running `ingest` again on the same files deletes existing chunks for those source files before re-inserting (idempotent).

**Source:** `src/python/pipeline/structurer.py`, `src/python/pipeline/chunker.py`

---

## Section 5: CLI Interface

**Entrypoint:** `src/python/pipeline/run.py`

| Command | Description |
|---------|-------------|
| `python run.py extract` | Extract all 533 `.note` files → `data/notes_md/raw/` |
| `python run.py extract --limit 20` | Extract first N files (for pilot) |
| `python run.py ingest` | Structure, chunk, and ingest cleaned files → ChromaDB |
| `python run.py ingest --dry-run` | Run ingestion without writing to ChromaDB |
| `python run.py status` | Report: raw count, cleaned count, ingested count, pending, extraction failures |

### End-to-end flow

```
1. python run.py extract --limit 20          # Extract pilot batch
2. [Claude Code session: clean pilot batch]  # Review output quality
3. python run.py extract                     # Extract all 533
4. [Claude Code session: clean all]          # Batch cleaning
5. python run.py ingest                      # Chunk + ingest to ChromaDB
6. python run.py status                      # Verify everything landed
```

No `config/settings.json` or API keys needed — the Python pipeline makes no LLM calls. All intelligence comes from Claude Code sessions.

**Note:** CLAUDE.md mentions `docs/notabilityNotes/mdDocs/` as the output location for converted notes. This spec uses `data/notes_md/` instead to keep processed outputs under `data/` (separate from source documents in `docs/`). CLAUDE.md should be updated to reflect this.

---

## File Map

| File | Purpose |
|------|---------|
| `src/python/pipeline/run.py` | CLI entrypoint (extract, ingest, status) |
| `src/python/pipeline/extractor.py` | .note → raw .md extraction |
| `src/python/pipeline/clinical_dictionary.py` | Term lists + folder-to-category mapping |
| `src/python/pipeline/structurer.py` | YAML front matter validation + normalisation |
| `src/python/pipeline/chunker.py` | Text splitting + ChromaDB ingestion |
| `src/python/pipeline/cleaning_prompt.md` | Reusable Claude Code prompt template for OCR cleaning |
| `data/notes_md/raw/` | Raw extracted OCR text (intermediate) |
| `data/notes_md/cleaned/` | Cleaned text (Claude Code output) |
| `data/notes_md/extraction_log.json` | Extraction error log |
| `data/notes_md/ingestion_log.json` | Ingestion summary log |
| `data/chroma_db/` | ChromaDB persistent store |

---

## Dependencies

Already in `pyproject.toml`:
- `chromadb` — vector store
- `langchain-text-splitters` — chunking

Additional (must be added to `pyproject.toml`):
- `pyyaml` — YAML front matter parsing

Stdlib (no install):
- `plistlib` — binary plist parsing
- `zipfile` — ZIP archive handling

---

## Success Criteria

- [ ] `python run.py extract` processes all 533 `.note` files, writes raw `.md` to `data/notes_md/raw/`
- [ ] Extraction handles missing HandwritingIndex, empty pages, duplicate folders gracefully
- [ ] Claude Code cleaning pilot (~15–20 files) produces correctly cleaned output with appropriate category assignments
- [ ] User reviews and approves pilot quality before full batch
- [ ] Full cleaning batch completes for all 533 files
- [ ] `python run.py ingest` chunks and ingests all cleaned files into ChromaDB
- [ ] `python run.py status` confirms all files extracted, cleaned, and ingested
- [ ] ChromaDB collection `"paramedic_notes"` is queryable with correct metadata
- [ ] Re-running `ingest` is idempotent (no duplicate chunks)
- [ ] All `[REVIEW_REQUIRED]` flags are surfaced in the ingestion log
