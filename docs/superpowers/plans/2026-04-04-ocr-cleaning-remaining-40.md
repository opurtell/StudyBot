# OCR Cleaning — Remaining 40 Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean the remaining 40 uncleaned raw OCR notes (25 in CXA310 Bio 2, 15 in CXA206 Bio 1) using Claude Code subagents following the established cleaning prompt.

**Architecture:** This is a continuation of the existing OCR cleaning pipeline (Phase 1C). The cleaning is performed by Claude Code subagents reading raw markdown from `data/notes_md/raw/`, applying OCR correction rules, and writing cleaned files to `data/notes_md/cleaned/`. No Python code changes required — this is a data-processing task using the existing prompt template at `src/python/pipeline/cleaning_prompt.md`.

**Tech Stack:** Claude Code subagents, YAML front matter, markdown

---

## Context for the Executing Agent

### What You Are Doing
Cleaning OCR-extracted handwritten paramedic study notes. The raw files contain garbled text from handwriting recognition — your job is to fix OCR artefacts only (character substitutions, broken words, garbled drug names). You must NEVER rephrase, reword, add, or remove content. You must NEVER correct factual or clinical errors.

### File Format
- **Input:** `data/notes_md/raw/<subject>/<filename>.md` — YAML front matter + raw OCR text
- **Output:** `data/notes_md/cleaned/<subject>/<filename>.md` — YAML front matter with added `categories` and `review_flags` + cleaned text
- **Example cleaned file:** `data/notes_md/cleaned/CXA206 Bio 1/CXA204 Endocrine Workshop 2022_STUDENT  copy.md`

### Categories
Both CXA206 Bio 1 and CXA310 Bio 2 map to **Pathophysiology** as the default category (see `clinical_dictionary.py` line 39 and 42). Assign 1–3 categories per note based on actual content from this list:
- Clinical Guidelines
- Medication Guidelines
- Operational Guidelines
- Clinical Skills
- Pathophysiology
- Pharmacology
- ECGs
- General Paramedicine

### OCR Error Patterns Seen in These Files
Based on sample inspection of the raw files, expect:
- `A` or `t` for `↑` (up arrow) and `Jr` or `a` for `↓` (down arrow)
- `inglamation` / `inslamation` → `inflammation`
- `releig` → `relief`
- `gibe` → `fibre` (A-delta fibre, C-fibre)
- `all` → `cell` (target cell)
- `unter` → `water`
- `bleed` → `blood`
- `Bal` / `But` → `BGL` (blood glucose level)
- `Cast` → `Ca²⁺` (calcium)
- `Nat` → `Na⁺` (sodium)
- `Kt` → `K⁺` (potassium)
- `honadutrophin` → `gonadotrophin`
- `Citeinising` → `Luteinising`
- `sedbuk` → `feedback`
- `sunction` / `sanction` → `function`
- `Her moves` / `hermon` → `hormones`
- `ant tinier` / `Annie` → `anterior`
- `Rituitary` / `Rit` → `pituitary`
- `crit` / `CRH` substitution confusion
- `Cox` / `COX` (cyclooxygenase) — preserve correct casing
- `NSAIDs` → preserve correct casing
- Numbers garbled in OCR: `23mths` → `2–3mths`, `73 meths` → `3 months`, `2504` → `>50%`
- `eye` → `e.g.` when used as abbreviation
- `sits tx` → `this tx` or `previous tx`
- `weightless` → `weight loss`
- `chat formation` → `clot formation`
- `thot slush` → `hot flush`
- `thendade` → `headache`
- `slight` → likely correct in context, check carefully

---

## Files to Clean

### CXA206 Bio 1 (15 files)

| # | File |
|---|------|
| 1 | `CXA206 Bio 1/Week 12 Renal System.md` |
| 2 | `CXA206 Bio 1/Week 2 Defences.md` |
| 3 | `CXA206 Bio 1/Week 2 defences 2.md` |
| 4 | `CXA206 Bio 1/Week 3 Helathcare Associated Diseases.md` |
| 5 | `CXA206 Bio 1/Week 3 defences immunisation .md` |
| 6 | `CXA206 Bio 1/Week 4 Nervous somatosensory pathways.md` |
| 7 | `CXA206 Bio 1/Week 4 Nervous system Action potentials.md` |
| 8 | `CXA206 Bio 1/Week 4 nervous autonomic.md` |
| 9 | `CXA206 Bio 1/Week 4 nervous system  somatomotor pathways.md` |
| 10 | `CXA206 Bio 1/Week 5 Nervous dysfunction.md` |
| 11 | `CXA206 Bio 1/Week 6 Endocrine.md` |
| 12 | `CXA206 Bio 1/Week 8 Cardiovascular.md` |
| 13 | `CXA206 Bio 1/Week 9 Cardiovascular.md` |
| 14 | `CXA206 Bio 1/Week 9 Heart Failure and Blood.md` |
| 15 | `CXA206 Bio 1/Wound Care webinar.md` |

### CXA310 Bio 2 (25 files)

| # | File |
|---|------|
| 1 | `CXA310 Bio 2/CXA310 Workshop 1 st.md` |
| 2 | `CXA310 Bio 2/CXA310 Workshop 2- student 2022.md` |
| 3 | `CXA310 Bio 2/CXA310 Workshop 3 st.md` |
| 4 | `CXA310 Bio 2/Circulatory shock, blood and fluids.md` |
| 5 | `CXA310 Bio 2/Female Reproductive system.md` |
| 6 | `CXA310 Bio 2/Fertilisation, infertility and reproductive pharmacology.md` |
| 7 | `CXA310 Bio 2/Geriatric Pharmacology.md` |
| 8 | `CXA310 Bio 2/Head and spinal injuries and stroke.md` |
| 9 | `CXA310 Bio 2/Male reproductive system.md` |
| 10 | `CXA310 Bio 2/Microbiology.md` |
| 11 | `CXA310 Bio 2/Mitosis and meiosis.md` |
| 12 | `CXA310 Bio 2/Musculoskeletal dysfunction 2 - Altered joint structure.md` |
| 13 | `CXA310 Bio 2/Notes 4 Sep 2022.md` |
| 14 | `CXA310 Bio 2/Oncology - development and progression of cancer and clinical considerations.md` |
| 15 | `CXA310 Bio 2/Pain.md` |
| 16 | `CXA310 Bio 2/Reproductive microbiology.md` |
| 17 | `CXA310 Bio 2/Revision notes.md` |
| 18 | `CXA310 Bio 2/Week 1 tut bio.md` |
| 19 | `CXA310 Bio 2/Week 2 Head and spinal injuries and stroke.md` |
| 20 | `CXA310 Bio 2/Week 3 Diabetes Mellitus.md` |
| 21 | `CXA310 Bio 2/Week 3 Nutrition and Diabetes.md` |
| 22 | `CXA310 Bio 2/Week 3 Nutrition.md` |
| 23 | `CXA310 Bio 2/Week 4 Digestive.md` |
| 24 | `CXA310 Bio 2/Week 5 gastroenterology.md` |
| 25 | `CXA310 Bio 2/Week 6 musculoskeletal .md` |

---

## Tasks

### Task 1: Clean CXA206 Bio 1 Batch A (5 files) — Defences and Nervous System

**Files to clean:**
- `data/notes_md/raw/CXA206 Bio 1/Week 2 Defences.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 2 defences 2.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 3 Helathcare Associated Diseases.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 3 defences immunisation .md`
- `data/notes_md/raw/CXA206 Bio 1/Week 5 Nervous dysfunction.md`

- [ ] **Step 1: Dispatch a subagent to clean these 5 files**

Give the subagent:
- The exact file paths listed above
- The default category: Pathophysiology
- The clinical terms from `clinical_dictionary.py` for Pathophysiology: haemorrhage, hypovolaemia, perfusion, ventilation, oxygenation, haemoglobin, erythrocyte, leukocyte, myocardium, cerebral, renal, hepatic, ischaemia, infarction, oedema, inflammation, coagulation
- The cleaning rules from `src/python/pipeline/cleaning_prompt.md` (OCR errors only, flag uncertain corrections, assign categories, write to `data/notes_md/cleaned/`)
- The OCR error patterns listed in the Context section above

- [ ] **Step 2: Verify 5 cleaned files were written**

Run: `ls data/notes_md/cleaned/CXA206\ Bio\ 1/Week\ 2\ Defences.md data/notes_md/cleaned/CXA206\ Bio\ 1/Week\ 2\ defences\ 2.md data/notes_md/cleaned/CXA206\ Bio\ 1/Week\ 3\ Helathcare\ Associated\ Diseases.md data/notes_md/cleaned/CXA206\ Bio\ 1/Week\ 3\ defences\ immunisation\ .md data/notes_md/cleaned/CXA206\ Bio\ 1/Week\ 5\ Nervous\ dysfunction.md`
Expected: All 5 files exist

- [ ] **Step 3: Spot-check 1 cleaned file for quality**

Read one cleaned file and verify:
1. YAML front matter has: title, subject, categories, source_file, last_modified, review_flags
2. OCR corrections look reasonable (no content added/removed)
3. Categories make sense for the content
4. Review flags are present for uncertain corrections but not excessive

---

### Task 2: Clean CXA206 Bio 1 Batch B (5 files) — Nervous System Pathways

**Files to clean:**
- `data/notes_md/raw/CXA206 Bio 1/Week 4 Nervous somatosensory pathways.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 4 Nervous system Action potentials.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 4 nervous autonomic.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 4 nervous system  somatomotor pathways.md`
- `data/notes_md/raw/CXA206 Bio 1/Wound Care webinar.md`

- [ ] **Step 1: Dispatch a subagent to clean these 5 files**

Same instructions as Task 1 Step 1, but with these file paths.

- [ ] **Step 2: Verify 5 cleaned files were written**

Check all 5 output files exist in `data/notes_md/cleaned/CXA206 Bio 1/`.

- [ ] **Step 3: Spot-check 1 cleaned file for quality**

Same checks as Task 1 Step 3.

---

### Task 3: Clean CXA206 Bio 1 Batch C (5 files) — Endocrine, Cardiovascular, Renal

**Files to clean:**
- `data/notes_md/raw/CXA206 Bio 1/Week 6 Endocrine.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 8 Cardiovascular.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 9 Cardiovascular.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 9 Heart Failure and Blood.md`
- `data/notes_md/raw/CXA206 Bio 1/Week 12 Renal System.md`

- [ ] **Step 1: Dispatch a subagent to clean these 5 files**

Same instructions as Task 1 Step 1, but with these file paths. Pay particular attention to:
- Endocrine file has many hormone name OCR errors (see Context section)
- Cardiovascular files may have cardiac term garbling
- Renal file may have kidney/fluid term garbling

- [ ] **Step 2: Verify 5 cleaned files were written**

Check all 5 output files exist in `data/notes_md/cleaned/CXA206 Bio 1/`.

- [ ] **Step 3: Spot-check the Endocrine cleaned file**

Read `data/notes_md/cleaned/CXA206 Bio 1/Week 6 Endocrine.md` and verify hormone names are corrected (thyroxine, TSH, ACTH, FSH, LH, ADH, etc.) without content changes.

- [ ] **Step 4: Verify CXA206 Bio 1 is now fully cleaned**

Run: `diff <(ls "data/notes_md/raw/CXA206 Bio 1/" | sort) <(ls "data/notes_md/cleaned/CXA206 Bio 1/" | sort)`
Expected: No output (all files have cleaned counterparts)

---

### Task 4: Clean CXA310 Bio 2 Batch A (8 files) — Workshops and General Topics

**Files to clean:**
- `data/notes_md/raw/CXA310 Bio 2/CXA310 Workshop 1 st.md`
- `data/notes_md/raw/CXA310 Bio 2/CXA310 Workshop 2- student 2022.md`
- `data/notes_md/raw/CXA310 Bio 2/CXA310 Workshop 3 st.md`
- `data/notes_md/raw/CXA310 Bio 2/Microbiology.md`
- `data/notes_md/raw/CXA310 Bio 2/Mitosis and meiosis.md`
- `data/notes_md/raw/CXA310 Bio 2/Notes 4 Sep 2022.md`
- `data/notes_md/raw/CXA310 Bio 2/Revision notes.md`
- `data/notes_md/raw/CXA310 Bio 2/Week 1 tut bio.md`

- [ ] **Step 1: Dispatch a subagent to clean these 8 files**

Same instructions as Task 1 Step 1, but with these file paths. Default category is Pathophysiology.

- [ ] **Step 2: Verify 8 cleaned files were written**

Check all 8 output files exist in `data/notes_md/cleaned/CXA310 Bio 2/`.

- [ ] **Step 3: Spot-check 1 cleaned file for quality**

Same checks as Task 1 Step 3.

---

### Task 5: Clean CXA310 Bio 2 Batch B (9 files) — Reproductive, Oncology, Pain

**Files to clean:**
- `data/notes_md/raw/CXA310 Bio 2/Female Reproductive system.md`
- `data/notes_md/raw/CXA310 Bio 2/Fertilisation, infertility and reproductive pharmacology.md`
- `data/notes_md/raw/CXA310 Bio 2/Male reproductive system.md`
- `data/notes_md/raw/CXA310 Bio 2/Reproductive microbiology.md`
- `data/notes_md/raw/CXA310 Bio 2/Oncology - development and progression of cancer and clinical considerations.md`
- `data/notes_md/raw/CXA310 Bio 2/Pain.md`
- `data/notes_md/raw/CXA310 Bio 2/Geriatric Pharmacology.md`
- `data/notes_md/raw/CXA310 Bio 2/Musculoskeletal dysfunction 2 - Altered joint structure.md`
- `data/notes_md/raw/CXA310 Bio 2/Week 6 musculoskeletal .md`

- [ ] **Step 1: Dispatch a subagent to clean these 9 files**

Same instructions as Task 1 Step 1, but with these file paths. Pay particular attention to:
- Pain file has many drug name OCR errors (NSAIDs, COX, prostaglandins, opioids, paracetamol, lidocaine)
- Reproductive files may have hormone/organ term garbling
- Pharmacology-related files may need `Pharmacology` as secondary category

- [ ] **Step 2: Verify 9 cleaned files were written**

Check all 9 output files exist in `data/notes_md/cleaned/CXA310 Bio 2/`.

- [ ] **Step 3: Spot-check the Pain cleaned file**

Read `data/notes_md/cleaned/CXA310 Bio 2/Pain.md` and verify drug names (NSAIDs, COX-1, COX-2, prostaglandins, opioids, paracetamol, lidocaine, bupivacaine, ziconotide) are corrected without content changes.

---

### Task 6: Clean CXA310 Bio 2 Batch C (8 files) — Systems and Clinical Topics

**Files to clean:**
- `data/notes_md/raw/CXA310 Bio 2/Circulatory shock, blood and fluids.md`
- `data/notes_md/raw/CXA310 Bio 2/Head and spinal injuries and stroke.md`
- `data/notes_md/raw/CXA310 Bio 2/Week 2 Head and spinal injuries and stroke.md`
- `data/notes_md/raw/CXA310 Bio 2/Week 3 Diabetes Mellitus.md`
- `data/notes_md/raw/CXA310 Bio 2/Week 3 Nutrition and Diabetes.md`
- `data/notes_md/raw/CXA310 Bio 2/Week 3 Nutrition.md`
- `data/notes_md/raw/CXA310 Bio 2/Week 4 Digestive.md`
- `data/notes_md/raw/CXA310 Bio 2/Week 5 gastroenterology.md`

- [ ] **Step 1: Dispatch a subagent to clean these 8 files**

Same instructions as Task 1 Step 1, but with these file paths. Pay particular attention to:
- Circulatory shock file likely has fluid/resuscitation terminology
- Diabetes files likely have BGL/insulin/glucagon garbling
- Digestive/gastroenterology files may have organ and enzyme name garbling

- [ ] **Step 2: Verify 8 cleaned files were written**

Check all 8 output files exist in `data/notes_md/cleaned/CXA310 Bio 2/`.

- [ ] **Step 3: Spot-check 1 cleaned file for quality**

Same checks as Task 1 Step 3.

---

### Task 7: Final Verification

- [ ] **Step 1: Verify all 40 files are cleaned**

Run: `diff <(find data/notes_md/raw -name '*.md' | sed 's|data/notes_md/raw/||' | sort) <(find data/notes_md/cleaned -name '*.md' | sed 's|data/notes_md/cleaned/||' | sort) | grep '^<'`
Expected: No output (all raw files have cleaned counterparts)

- [ ] **Step 2: Count total cleaned files**

Run: `find data/notes_md/cleaned -name '*.md' | wc -l`
Expected: 392

- [ ] **Step 3: Print final summary**

Report:
- Total files cleaned this session: 40
- Total files now cleaned: 392/392 (100%)
- CXA206 Bio 1: 33/33 cleaned
- CXA310 Bio 2: 25/25 cleaned
- OCR cleaning pipeline is COMPLETE
