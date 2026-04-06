# Full Extraction and Ingestion — Operational Plan

**Goal:** Extract all 533 `.note` files, clean them, and ingest into ChromaDB.

---

## Step 1: Full Extraction

```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py extract
```

Expected: ~500+ successes, ~30–50 failures (PDF-only notes). Check `data/notes_md/extraction_log.json` for failures — all should be "No HandwritingIndex found".

Verify:
```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py status
```

Should show raw count ~500+, cleaned 0, pending ~500+.

---

## Step 2: Pilot Cleaning (if not already done)

Run the pilot cleaning session using `Guides/PILOT_CLEANING_SESSION.md`.
Review quality before proceeding to full batch.

---

## Step 3: Full Cleaning

This is the most time-consuming step. Run multiple Claude Code sessions, one per folder group.

### Folder Groups for Cleaning Sessions

Group by semester/subject to keep batches manageable (~30–40 files each):

| Session | Folders | ~Files |
|---------|---------|--------|
| 1 | ACTAS/Induction, ACTAS/Study Block 2, ACTAS/Study Block 3, ACTAS/Finals | ~46 |
| 2 | CSA236 Pharmacology | ~10 |
| 3 | Paramedics 2021 sem 1 (all subfolders) | ~87 |
| 4 | Paramedics 2021 sem 2 (all subfolders) | ~92 |
| 5 | Paramedics 2021 sem 3 (all subfolders) | ~66 |
| 6 | Paramedics 2022 Sem 1 (all subfolders) | ~70 |
| 7 | Paramedics 2022 Sem 2 (all subfolders) | ~47 |
| 8 | Paramedics 2022 Sem 3 (all subfolders) | ~44 |
| 9 | General Paramedicine + remaining folders | ~71 |

**Total: ~533 files across ~9 sessions**

### Prompt Template for Each Session

```
I'm working on the Clinical Recall Assistant project. Follow the instructions
in `src/python/pipeline/cleaning_prompt.md` to clean OCR-extracted notability notes.

**Scope:** Only clean files in these folders under `data/notes_md/raw/`:
- [list specific folders for this session]

Skip any file that already has a cleaned counterpart in `data/notes_md/cleaned/`.

After cleaning, print a summary: files cleaned, files skipped, total review flags.
Do not ingest into ChromaDB or modify any code files.
```

### Resumability

The cleaning prompt is designed to be resumable — it skips files that already have a cleaned counterpart. If a session crashes or runs out of context, start a new session with the same prompt and it picks up where it left off.

---

## Step 4: Ingestion

Once all files are cleaned:

```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py ingest --dry-run
```

Review the dry-run output for any validation failures. Then:

```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py ingest
```

Expected: ~500+ files ingested, ~2000–3000 total chunks.

---

## Step 5: Verification

```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py status
```

Should show: raw ~500+, cleaned ~500+, ChromaDB chunks ~2000+.

Query ChromaDB to verify:
```bash
python3 -c "
import chromadb
client = chromadb.PersistentClient(path='data/chroma_db')
col = client.get_collection('paramedic_notes')
print(f'Total chunks: {col.count()}')
results = col.query(query_texts=['cardiac arrest treatment'], n_results=3)
for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
    print(f'[{meta[\"source_file\"]}] {doc[:120]}...')
"
```

---

## Step 6: Review Flags

Check `data/notes_md/ingestion_log.json` for files with `has_review_flag: true`. Review the flagged corrections in the cleaned files and resolve any that look wrong.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Extraction crashes | Check extraction_log.json — per-file errors don't stop the batch |
| Too many OCR errors | Clinical dictionary may need extending — add terms to `clinical_dictionary.py` |
| Low chunk count | Some notes may be very short — check a few raw files for empty OCR text |
| ChromaDB query returns nothing | Verify collection name is "paramedic_notes" and chunks have documents (not just metadata) |
