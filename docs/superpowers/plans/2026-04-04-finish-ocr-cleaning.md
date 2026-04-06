# Finish OCR Cleaning — Final 40 Files

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean the remaining 40 raw OCR-extracted Notability notes (15 in CXA206 Bio 1, 25 in CXA310 Bio 2), then ingest all 392 cleaned files into ChromaDB.

**Architecture:** Follow the existing cleaning workflow defined in `src/python/pipeline/cleaning_prompt.md`. Use parallel subagents to clean files in batches of 5–10, grouped by folder. After cleaning, run the pipeline's `ingest` command to chunk and load into ChromaDB.

**Tech Stack:** Python, YAML front matter, ChromaDB, Claude Code subagents for OCR cleaning

---

## Context for the Implementer

### What is this?
Handwritten paramedic study notes were extracted from Notability `.note` files (ZIP archives with OCR text). The OCR output is garbled — character substitutions, broken words, missing spaces. A cleaning process fixes OCR artefacts while preserving the original content.

### What's already done?
- 476 `.note` files extracted → 453 raw `.md` files (23 failed — PDF-only, no OCR)
- 352 of those raw files have been cleaned and written to `data/notes_md/cleaned/`
- Only 40 files remain: 15 in `CXA206 Bio 1` and 25 in `CXA310 Bio 2`

### Where things live
- **Raw files:** `data/notes_md/raw/<subject_folder>/<file>.md`
- **Cleaned files:** `data/notes_md/cleaned/<subject_folder>/<file>.md`
- **Cleaning rules:** `src/python/pipeline/cleaning_prompt.md`
- **Clinical dictionary:** `src/python/pipeline/clinical_dictionary.py`
- **Pipeline CLI:** `src/python/pipeline/run.py`

### Cleaning rules (summary)
1. Fix OCR errors ONLY — never rephrase, reword, add, or remove content
2. Common OCR patterns: `8`↔`g`, `1`↔`l`, `rn`↔`m`, `0`↔`O`, broken words, missing spaces, stray punctuation
3. Flag uncertain corrections inline with `[REVIEW_REQUIRED: <original> → <correction>]`
4. Assign 1–3 categories from the canonical list in `clinical_dictionary.py`
5. Output YAML front matter with: title, subject, categories, source_file, last_modified, review_flags

### Subject-to-category mapping
- `CXA206 Bio 1` → default: **Pathophysiology**
- `CXA310 Bio 2` → default: **Pathophysiology**
- May also need: Pharmacology, Clinical Guidelines, Clinical Skills depending on content

---

## File List: Remaining Un-Cleaned Files

### CXA206 Bio 1 (15 files)
1. `CXA206 Bio 1/Week 12 Renal System.md`
2. `CXA206 Bio 1/Week 2 Defences.md`
3. `CXA206 Bio 1/Week 2 defences 2.md`
4. `CXA206 Bio 1/Week 3 Helathcare Associated Diseases.md`
5. `CXA206 Bio 1/Week 3 defences immunisation .md`
6. `CXA206 Bio 1/Week 4 Nervous somatosensory pathways.md`
7. `CXA206 Bio 1/Week 4 Nervous system Action potentials.md`
8. `CXA206 Bio 1/Week 4 nervous autonomic.md`
9. `CXA206 Bio 1/Week 4 nervous system  somatomotor pathways.md`
10. `CXA206 Bio 1/Week 5 Nervous dysfunction.md`
11. `CXA206 Bio 1/Week 6 Endocrine.md`
12. `CXA206 Bio 1/Week 8 Cardiovascular.md`
13. `CXA206 Bio 1/Week 9 Cardiovascular.md`
14. `CXA206 Bio 1/Week 9 Heart Failure and Blood.md`
15. `CXA206 Bio 1/Wound Care webinar.md`

### CXA310 Bio 2 (25 files)
1. `CXA310 Bio 2/CXA310 Workshop 1 st.md`
2. `CXA310 Bio 2/CXA310 Workshop 2- student 2022.md`
3. `CXA310 Bio 2/CXA310 Workshop 3 st.md`
4. `CXA310 Bio 2/Circulatory shock, blood and fluids.md`
5. `CXA310 Bio 2/Female Reproductive system.md`
6. `CXA310 Bio 2/Fertilisation, infertility and reproductive pharmacology.md`
7. `CXA310 Bio 2/Geriatric Pharmacology.md`
8. `CXA310 Bio 2/Head and spinal injuries and stroke.md`
9. `CXA310 Bio 2/Male reproductive system.md`
10. `CXA310 Bio 2/Microbiology.md`
11. `CXA310 Bio 2/Mitosis and meiosis.md`
12. `CXA310 Bio 2/Musculoskeletal dysfunction 2 - Altered joint structure.md`
13. `CXA310 Bio 2/Notes 4 Sep 2022.md`
14. `CXA310 Bio 2/Oncology - development and progression of cancer and clinical considerations.md`
15. `CXA310 Bio 2/Pain.md`
16. `CXA310 Bio 2/Reproductive microbiology.md`
17. `CXA310 Bio 2/Revision notes.md`
18. `CXA310 Bio 2/Week 1 tut bio.md`
19. `CXA310 Bio 2/Week 2 Head and spinal injuries and stroke.md`
20. `CXA310 Bio 2/Week 3 Diabetes Mellitus.md`
21. `CXA310 Bio 2/Week 3 Nutrition and Diabetes.md`
22. `CXA310 Bio 2/Week 3 Nutrition.md`
23. `CXA310 Bio 2/Week 4 Digestive.md`
24. `CXA310 Bio 2/Week 5 gastroenterology.md`
25. `CXA310 Bio 2/Week 6 musculoskeletal .md`

---

## Tasks

### Task 1: Clean CXA206 Bio 1 — Batch 1 (Files 1–8)

**Files:**
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 12 Renal System.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 2 Defences.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 2 defences 2.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 3 Helathcare Associated Diseases.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 3 defences immunisation .md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 4 Nervous somatosensory pathways.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 4 Nervous system Action potentials.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 4 nervous autonomic.md`
- Read: `src/python/pipeline/cleaning_prompt.md` (for rules)
- Read: `src/python/pipeline/clinical_dictionary.py` (for terms)
- Write: `data/notes_md/cleaned/CXA206 Bio 1/<filename>.md` for each file

- [ ] **Step 1: Read the cleaning rules and clinical dictionary**

Read `src/python/pipeline/cleaning_prompt.md` and `src/python/pipeline/clinical_dictionary.py` to understand the cleaning format, rules, and relevant clinical terms (focus on the "Pathophysiology" and "Pharmacology" term lists).

- [ ] **Step 2: Read all 8 raw files**

Read each of the 8 raw files listed above. Note any common OCR patterns across the batch.

- [ ] **Step 3: Clean files 1–4 using parallel subagents**

For each file:
1. Read the raw content
2. Fix OCR errors only — character substitutions, broken words, missing spaces, stray punctuation
3. Assign 1–3 categories based on content (likely Pathophysiology + possibly Pharmacology or Clinical Guidelines)
4. Flag uncertain corrections with `[REVIEW_REQUIRED: <original> → <correction>]` inline
5. Write to `data/notes_md/cleaned/CXA206 Bio 1/<same filename>.md` with proper YAML front matter

YAML front matter format:
```yaml
---
title: "<from raw file>"
subject: "<from raw file>"
categories:
  - "Pathophysiology"
  - "<secondary if applicable>"
source_file: "<from raw file>"
last_modified: "<from raw file>"
review_flags:
  - "<original> → <correction>"
---

<cleaned text>
```

- [ ] **Step 4: Clean files 5–8 using parallel subagents**

Same process as Step 3.

- [ ] **Step 5: Verify batch output**

For 2–3 of the cleaned files, read both raw and cleaned versions side by side. Check:
- OCR fixes are correct (drug names, clinical terms restored)
- No content was added or removed
- Categories make sense for the content
- Review flags are reasonable (not over-cautious, not missing obvious errors)
- YAML front matter is well-formed

---

### Task 2: Clean CXA206 Bio 1 — Batch 2 (Files 9–15)

**Files:**
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 4 nervous system  somatomotor pathways.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 5 Nervous dysfunction.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 6 Endocrine.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 8 Cardiovascular.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 9 Cardiovascular.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Week 9 Heart Failure and Blood.md`
- Read: `data/notes_md/raw/CXA206 Bio 1/Wound Care webinar.md`
- Write: `data/notes_md/cleaned/CXA206 Bio 1/<filename>.md` for each

- [ ] **Step 1: Read all 7 raw files**

- [ ] **Step 2: Clean files 9–12 using parallel subagents**

Same cleaning process as Task 1.

- [ ] **Step 3: Clean files 13–15 using parallel subagents**

Same cleaning process.

- [ ] **Step 4: Verify CXA206 Bio 1 is complete**

```bash
find data/notes_md/raw/CXA206\ Bio\ 1 -name "*.md" -type f | wc -l
find data/notes_md/cleaned/CXA206\ Bio\ 1 -name "*.md" -type f | wc -l
```

Both should print 33 (18 already cleaned + 15 new).

---

### Task 3: Clean CXA310 Bio 2 — Batch 1 (Files 1–8)

**Files:**
- Read: `data/notes_md/raw/CXA310 Bio 2/CXA310 Workshop 1 st.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/CXA310 Workshop 2- student 2022.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/CXA310 Workshop 3 st.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Circulatory shock, blood and fluids.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Female Reproductive system.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Fertilisation, infertility and reproductive pharmacology.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Geriatric Pharmacology.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Head and spinal injuries and stroke.md`
- Write: `data/notes_md/cleaned/CXA310 Bio 2/<filename>.md` for each

- [ ] **Step 1: Read all 8 raw files**

- [ ] **Step 2: Clean files 1–4 using parallel subagents**

Same cleaning process. CXA310 Bio 2 default category is Pathophysiology. Some files (e.g. Geriatric Pharmacology, Fertilisation pharmacology) may also warrant Pharmacology as a secondary category.

- [ ] **Step 3: Clean files 5–8 using parallel subagents**

- [ ] **Step 4: Spot-check 2 cleaned files**

Read raw + cleaned side by side for 2 files.

---

### Task 4: Clean CXA310 Bio 2 — Batch 2 (Files 9–17)

**Files:**
- Read: `data/notes_md/raw/CXA310 Bio 2/Male reproductive system.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Microbiology.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Mitosis and meiosis.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Musculoskeletal dysfunction 2 - Altered joint structure.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Notes 4 Sep 2022.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Oncology - development and progression of cancer and clinical considerations.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Pain.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Reproductive microbiology.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Revision notes.md`
- Write: `data/notes_md/cleaned/CXA310 Bio 2/<filename>.md` for each

- [ ] **Step 1: Read all 9 raw files**

- [ ] **Step 2: Clean files 9–13 using parallel subagents**

- [ ] **Step 3: Clean files 14–17 using parallel subagents**

- [ ] **Step 4: Spot-check 2 cleaned files**

---

### Task 5: Clean CXA310 Bio 2 — Batch 3 (Files 18–25)

**Files:**
- Read: `data/notes_md/raw/CXA310 Bio 2/Week 1 tut bio.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Week 2 Head and spinal injuries and stroke.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Week 3 Diabetes Mellitus.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Week 3 Nutrition and Diabetes.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Week 3 Nutrition.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Week 4 Digestive.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Week 5 gastroenterology.md`
- Read: `data/notes_md/raw/CXA310 Bio 2/Week 6 musculoskeletal .md`
- Write: `data/notes_md/cleaned/CXA310 Bio 2/<filename>.md` for each

- [ ] **Step 1: Read all 8 raw files**

- [ ] **Step 2: Clean files 18–21 using parallel subagents**

- [ ] **Step 3: Clean files 22–25 using parallel subagents**

- [ ] **Step 4: Verify CXA310 Bio 2 is complete**

```bash
find data/notes_md/raw/CXA310\ Bio\ 2 -name "*.md" -type f | wc -l
find data/notes_md/cleaned/CXA310\ Bio\ 2 -name "*.md" -type f | wc -l
```

Both should print 25 (0 already cleaned + 25 new).

---

### Task 6: Final Verification and Summary

- [ ] **Step 1: Run pipeline status**

```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py status
```

Expected output:
```
Raw extracted:       392
Extraction failures: 23
Cleaned:             392
Pending cleaning:    0
ChromaDB chunks:     0
```

- [ ] **Step 2: Confirm zero pending files**

```bash
find data/notes_md/raw -name "*.md" -type f | sed 's|data/notes_md/raw/||' | sort > /tmp/raw.txt
find data/notes_md/cleaned -name "*.md" -type f | sed 's|data/notes_md/cleaned/||' | sort > /tmp/cleaned.txt
comm -23 /tmp/raw.txt /tmp/cleaned.txt
```

Expected: no output (all raw files have a cleaned counterpart).

- [ ] **Step 3: Print cleaning summary**

```bash
echo "Total cleaned files:"; find data/notes_md/cleaned -name "*.md" -type f | wc -l
echo "Review flags:"; grep -r "REVIEW_REQUIRED" data/notes_md/cleaned/ | wc -l
echo "Category distribution:"; grep -r "^  - " data/notes_md/cleaned/ | sort | uniq -c | sort -rn
```

- [ ] **Step 4: Update TODO.md**

In `TODO.md`, mark these items as complete:
- Phase 1C: "Implement LLM-powered cleaning agent" → this is done via Claude Code sessions, not a separate Python module. Mark `[x]` with note that cleaning is performed by Claude Code subagents using `cleaning_prompt.md`.
- Phase 1C: "`[REVIEW_REQUIRED: ...]` flagging for uncertain corrections" → `[x]`
- Phase 1C: "Test on known-bad OCR samples" → `[x]`
- Phase 1C: "Consider batch processing and rate limiting for 533 files" → `[x]` (done via Claude Code subagents)
- Phase 1F: "Run full pipeline on all 533 notes" → update to reflect 392 cleaned of 453 extracted (23 PDF-only failures, some Paramedics 2021 nested folders were flattened)

---

### Task 7: Ingest into ChromaDB (Optional — run after user confirmation)

This task ingests all 392 cleaned files into ChromaDB. **Only execute after user confirms they want ingestion to proceed.**

- [ ] **Step 1: Dry-run ingestion**

```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py ingest --dry-run
```

Review output for any validation failures.

- [ ] **Step 2: Run ingestion**

```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py ingest
```

Expected: ~392 files ingested, ~1500–2500 total chunks.

- [ ] **Step 3: Verify ChromaDB**

```bash
PYTHONPATH=src/python python3 src/python/pipeline/run.py status
```

Should show ChromaDB chunks > 0.

- [ ] **Step 4: Test query**

```bash
python3 -c "
import chromadb
client = chromadb.PersistentClient(path='data/chroma_db')
col = client.get_collection('paramedic_notes')
print(f'Total chunks: {col.count()}')
results = col.query(query_texts=['renal system pathophysiology'], n_results=3)
for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
    print(f'[{meta[\"source_file\"]}] {doc[:120]}...')
"
```

---

## Notes

- **Resumability:** If any cleaning session is interrupted, re-running the same batch will automatically skip already-cleaned files (the cleaning prompt checks for existing cleaned counterparts).
- **Review flags:** After ingestion, review files with `has_review_flag: true` in `data/notes_md/ingestion_log.json`. These contain uncertain OCR corrections that may need human review.
- **Quality gate:** The existing 352 cleaned files were spot-checked and look good. The same standard should be maintained for the final 40.
- **No code changes needed:** This plan only creates/edits markdown files in `data/notes_md/cleaned/` and optionally updates `TODO.md`. No Python or TypeScript code is modified.
