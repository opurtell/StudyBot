# OCR Cleaning Instructions

You are cleaning OCR-extracted handwritten notes from a paramedic student's Notability app. Follow these instructions precisely.

## Setup

1. Read `src/python/pipeline/clinical_dictionary.py` for the clinical term lists and category mappings.
2. Glob `data/notes_md/raw/**/*.md` to find all raw extracted files.
3. Glob `data/notes_md/cleaned/**/*.md` to find already-cleaned files.
4. Skip any raw file that already has a corresponding cleaned file at the same relative path under `data/notes_md/cleaned/`.
5. If there are no un-cleaned files remaining, print "All files already cleaned" and stop.

## Cleaning Rules

For each raw file:

1. **Read the file** — it has YAML front matter (title, subject, default_category, source_file, last_modified) followed by raw OCR text.

2. **Fix OCR errors only.** Common patterns:
   - Character substitutions: `8` for `g`, `1` for `l`, `rn` for `m`, `0` for `O`
   - Broken words: `mid azolam` → `midazolam`
   - Garbled drug names: `arniodarone` → `amiodarone`
   - Missing spaces: `cardiacarrest` → `cardiac arrest`
   - Stray punctuation: `2.5g W/10` → `2.5g IV/IO`
   - **Never** rephrase, reword, reorganise, add content, or remove content
   - **Never** correct factual or clinical errors — only fix OCR artefacts

3. **Flag uncertain corrections** with `[REVIEW_REQUIRED: <original> → <correction>]` inline. Use this when you're not confident the OCR error is what you think it is — especially for drug names and dosages. Do NOT flag every correction — only genuinely uncertain ones.

4. **Assign 1–3 categories** based on the note's actual content (not just the folder name). Choose from:
   - Clinical Guidelines
   - Medication Guidelines
   - Operational Guidelines
   - Clinical Skills
   - Pathophysiology
   - Pharmacology
   - ECGs
   - General Paramedicine

5. **Write the cleaned file** to `data/notes_md/cleaned/` at the same relative path. Create subdirectories as needed. Use this YAML front matter format:

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

Process files in batches of 5–10 using parallel subagents (Agent tool), grouped by folder. Each subagent should be given:
- The list of raw file paths to clean (as a list, not a glob pattern)
- The relevant clinical terms for the folder's default category (read from `clinical_dictionary.py`)
- These cleaning rules

Each subagent reads its assigned raw files, cleans them, and writes the output directly using the Write tool.

## After Cleaning

Print a summary:
- Files cleaned this session
- Files skipped (already done)
- Total review flags generated
- Category distribution of cleaned files

## Resumability

This prompt is designed to be run multiple times. It automatically skips already-cleaned files. If a previous session was interrupted, just run it again — it picks up where it left off.
