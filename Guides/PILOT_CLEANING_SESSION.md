# Pilot Cleaning Session — Claude Code Prompt

> Paste this into a fresh Claude Code session to clean the pilot batch of 16 raw notes.

---

I'm working on the Clinical Recall Assistant project. Follow the instructions in `src/python/pipeline/cleaning_prompt.md` to clean OCR-extracted notability notes.

**Scope:** Only process files currently in `data/notes_md/raw/` (pilot batch of ~16 files across Finals and Induction folders). Skip any file that already has a cleaned counterpart in `data/notes_md/cleaned/`.

**Important context:**
- These are handwritten paramedic study notes extracted via OCR — expect garbled drug names, broken words, character substitutions
- The clinical dictionary at `src/python/pipeline/clinical_dictionary.py` has correct spellings for common drugs and clinical terms
- Fix OCR errors only — never rephrase, reword, add content, or correct factual errors
- Flag uncertain corrections with `[REVIEW_REQUIRED: ...]` inline
- Assign 1–3 categories per note from the canonical list in the cleaning prompt

**After cleaning:** Print a summary — files cleaned, files skipped, total review flags. Then stop — do not ingest into ChromaDB or modify any code files.

---

## Quality Checklist

After the subagents finish, manually review 3–4 cleaned files for:

1. **OCR fixes are correct** — drug names, clinical terms restored without changing meaning
2. **No content was added or removed** — only OCR artefacts fixed
3. **Categories make sense** — based on note content, not just folder name
4. **Review flags are reasonable** — not too many (over-cautious), not too few (missing errors)
5. **Front matter format is correct** — title, subject, categories, source_file, last_modified, review_flags

If quality is poor, note specific issues so the cleaning prompt can be tuned before the full batch.
