# CMG Pipeline — Remaining Gaps

> **Updated 2026-04-03.** Previous "missing medicines" and "short CSM" issues have been resolved via extraction fixes. The remaining items are documented below.

## Resolved Issues

### 1. Medicine Dose Data — RESOLVED

All 35 MED entries from the navigation now have dose data. The original plan listed 12 "missing" medicines; investigation revealed the data existed in JS bundles but extraction was broken.

**Fixes applied:**
- Fixed `leveTiracetam` typo in `_MEDICINE_KEYWORDS` (`dose_tables.py:68`)
- Rewrote `_group_dose_texts` to use per-file processing, non-dose text boundaries, and medicine-header detection (1 mega-group → 538 focused groups)
- Added `pending_medicines` propagation for non-dose medicine headers preceding dose data
- Added `_extract_medicine_from_selectors` to attribute dose data via selector-route-to-medicine mapping for medicines whose `.EFF()` texts lack the keyword (Fentanyl, Calcium Chloride, Ipratropium, Salbutamol, Topical Anaesthetic)
- Removed 10 phantom keywords from `_MEDICINE_KEYWORDS` that have no MED entry in the app: `clopidogrel`, `ticagrelor`, `diazepam`, `furosemide`, `rocuronium`, `promethazine`, `sodium chloride`, `entinox`, `tetracaine`, `tranexamic`

**Result:** 36 medicines detected, 42/56 CMGs with dose data.

### 2. CMGs Without Dose Lookup — RESOLVED (correct behaviour)

14/56 CMGs have no dose data. This is correct — they fall into three categories:

| Category | CMGs | Explanation |
|----------|------|-------------|
| Genuinely medicine-free | Heat Abnormalities, Hypothermia, Limb Injuries, Assault, Falls, Psychogenic Non-Epileptic Seizures, CBRN/HAZMAT, Electric Shock | Assessment, procedures, or referral guidelines — no medicines involved |
| Flowchart decision trees | Cardiac Arrhythmias, ROSC: Paediatric | Routing guidelines that delegate to CMG 7/8 or CMG 4A — the target CMGs have the dose data |
| Defer to other CMGs | Abdominal Emergencies, Stroke, Behavioural and Mental Health Emergencies, Complicated Birth | Reference medicines indirectly ("Analgesia as per CMG 2", "Treat hypotension as per CMG 14") |

**No action needed.** The 6 CMGs flagged in the original plan (Adrenal Crisis, Stroke, Cardiac Arrhythmias, etc.) were based on incorrect assumptions about which medicines ACTAS carries. ACTAS does not carry Entinox, Tetracaine, or Tranexamic Acid.

### 3. CSM Short Content — 10/11 RESOLVED

10 of 11 short-content CSMs fixed by adding number-to-word normalization (`_normalize_for_matching`), word-overlap scoring (`_distinctive_overlap_score`), and improved selector fallback matching in `content_extractor.py`.

| CSM | Before | After | Fix |
|-----|--------|-------|-----|
| AirTraq (Endotracheal Intubation) | 35 chars | 1737 chars | Distinctive-word threshold |
| 15 Lead ECG Monitoring | 24 chars | 877 chars | "15" → "fifteen" normalization |
| CPAP | 44 chars | 2032 chars | Word-overlap selector match |
| Fundal Massage | 41 chars | 1254 chars | Word-overlap selector match |
| Blood Pressure (Palpate) | 38 chars | 858 chars | Word-overlap selector match |
| Applying Topical Anaesthetic Cream | 36 chars | 1276 chars | Word-overlap selector match |
| 12 Lead ECG Monitoring | 24 chars | 1025 chars | "12" → "twelve" normalization |
| Blood Pressure (Auscultate) | 41 chars | 858 chars | Word-overlap selector match |
| Mucosal Atomising Device (MAD) | 32 chars | 2031 chars | Distinctive-word threshold |
| Springfuser and Flow Control Tubing | 37 chars | 1056 chars | Word-overlap selector match |
| **Skills Matrix** | **15 chars** | **4,340 chars** | **Selector extractor now scans all bundles** |

## Outstanding Items

### 4. Flowcharts (Placeholder)

Flowchart extraction (Stage 5) is a mock implementation. The `flowcharts.py` module generates a single fake Mermaid graph. The actual CMG flowcharts are SVG images embedded in the Angular app.

**Priority:** Low — flowcharts are visual aids, not required for quiz generation.

### 5. Markdown Quality

The `html_to_markdown()` converter uses regex-based HTML stripping. Known issues:
- Tables render as flat text (no markdown table formatting)
- Flowchart decision points render as "YesNo" without visual separation
- Some header levels may be incorrect

**Action:** Consider replacing the regex-based `html_to_markdown()` in `template_parser.py` with a proper HTML parser (e.g., `markdownify` or `beautifulsoup4`). Check `pyproject.toml` for available libraries first.

**Priority:** Low — content is functional for quiz generation.

## Quick Reference

### Pipeline run command
```bash
PYTHONPATH=src/python python3 -m pipeline.cmg.orchestrator --stages all
```

### Key files
| File | Purpose |
|------|---------|
| `src/python/pipeline/cmg/orchestrator.py` | Pipeline entry point |
| `src/python/pipeline/cmg/dose_tables.py` | Medicine keyword list at `_MEDICINE_KEYWORDS` (line 26), selector-based extraction |
| `src/python/pipeline/cmg/content_extractor.py` | Content extraction + merge logic, route matching with number normalization |
| `src/python/pipeline/cmg/selector_extractor.py` | Selector-to-template mapping, now scans all JS bundles |
| `src/python/pipeline/cmg/structurer.py` | Dose matching logic (content-based, line 79) |
| `capture_assets.py` | Playwright site capture script (root level) |

### Test command
```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_cmg_extraction.py tests/python/test_cmg_pipeline.py -v
```
