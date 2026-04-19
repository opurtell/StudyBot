# ACTAS Qualifications Backfill — Review Document

**Date:** 2026-04-19
**Script:** `scripts/backfill_actas_qualifications.py`
**Data directory:** `data/services/actas/structured/`

This document lists every file and medicine entry that received `qualifications_required: ["ICP"]`
during the backfill. Please review and flag any errors in the **Status** column.

---

## Sources Consulted

Two sources were checked for ICP markers per the plan requirements:

| Source | Location | Result |
|--------|----------|--------|
| Quiz agent ICP prompt markers | `src/python/quiz/agent.py` (line 39 — skill_level detection logic) | Used to derive the authoritative ICP-only drug list. The agent's `skill_level` prompt text explicitly separates AP/ICP scope, confirming the 8-drug list below. |
| Structured JSON `profiles` / `scope` fields | `data/services/actas/structured/*.json` | Checked all 58 files. No file contains a `profiles` or `scope` field. ICP detection relies solely on `is_icp_only` (document level) and the drug list (medicine level). |

---

## How the Backfill Works

Two tagging rules are applied to every structured JSON in `data/services/actas/structured/`:

| Rule | Condition | Value written |
|------|-----------|---------------|
| Document level | `is_icp_only: true` | `qualifications_required: ["ICP"]` |
| Document level | `is_icp_only: false` | `qualifications_required: ["AP"]` |
| Medicine level | Medicine name is in ICP drug list (below) | `qualifications_required: ["ICP"]` on every dose entry |
| Medicine level | Medicine name is NOT in ICP drug list | `qualifications_required: ["AP"]` on every dose entry |

The script is idempotent — re-running it produces no change once the data is already tagged.

> **Note: `content_sections`-level tagging is deferred.** The `GuidelineDocument` schema (Task 3) supports per-section `qualifications_required`, but the current structured JSON files use a flat `content_markdown` string rather than structured `content_sections`. When content is later split into `ContentSection` objects, those sections will need their own `qualifications_required` backfill.

---

## ICP-Only Drug List

These medicines are restricted to Intensive Care Paramedic (ICP) scope in ACTAS:

| Medicine | Source of Authority |
|----------|-------------------|
| Adenosine | User sign-off 2026-04-19 |
| Amiodarone | User sign-off 2026-04-19 |
| Heparin | User sign-off 2026-04-19 |
| Hydrocortisone | User sign-off 2026-04-19 |
| Levetiracetam | User sign-off 2026-04-19 |
| Lignocaine | User sign-off 2026-04-19 |
| Sodium Bicarbonate | User sign-off 2026-04-19 |
| Suxamethonium | User sign-off 2026-04-19 |

---

## ICP-Only CMG Documents

These entire CMG files have `is_icp_only: true` set in the structured data and therefore
received `qualifications_required: ["ICP"]` at the document root level.

| File | CMG Number | Title | Source Evidence | Status |
|------|-----------|-------|----------------|--------|
| `CMG_3A_RSI__Rapid_Sequence_Intubation_.json` | 3A | RSI (Rapid Sequence Intubation) | `is_icp_only: true` in structured JSON (set during CMG extraction) | **Needs Review** |
| `CMG_3B_Intubation_Algorithm.json` | 3B | Intubation Algorithm | `is_icp_only: true` in structured JSON (set during CMG extraction) | **Needs Review** |

> **Action required:** Confirm that CMG 3A and 3B are ICP-only in full, or flag if AP practitioners
> have any permitted actions under these guidelines.

---

## ICP-Tagged Medicines by Drug

Each row shows a medicine that received `qualifications_required: ["ICP"]` on every dose entry
in the listed CMG files.

### Adenosine

| File | CMG | Title | Source Evidence | Status |
|------|-----|-------|----------------|--------|
| `CMG_8_Tachyarrhythmias.json` | 8 | Tachyarrhythmias | ICP drug list match | **Needs Review** |

### Amiodarone

| File | CMG | Title | Source Evidence | Status |
|------|-----|-------|----------------|--------|
| `CMG_4_Cardiac_Arrest__Adult.json` | 4 | Cardiac Arrest: Adult | ICP drug list match | **Needs Review** |
| `CMG_5_Cardiac_Arrest__Paediatric___12_years_old_.json` | 5 | Cardiac Arrest: Paediatric (<12 years old) | ICP drug list match | **Needs Review** |
| `CMG_8_Tachyarrhythmias.json` | 8 | Tachyarrhythmias | ICP drug list match | **Needs Review** |

### Heparin

| File | CMG | Title | Source Evidence | Status |
|------|-----|-------|----------------|--------|
| `CMG_16_Suspected_ACS__Acute_Coronary_Syndrome_.json` | 16 | Suspected ACS (Acute Coronary Syndrome) | ICP drug list match | **Needs Review** |
| `CMG_28_Home_Dialysis_Emergencies.json` | 28 | Home Dialysis Emergencies | ICP drug list match | **Needs Review** |

### Hydrocortisone

| File | CMG | Title | Source Evidence | Status |
|------|-----|-------|----------------|--------|
| `CMG_43_Adrenal_Crisis.json` | 43 | Adrenal Crisis | ICP drug list match | **Needs Review** |
| `CMG_9_Respiratory_Distress.json` | 9 | Respiratory Distress | ICP drug list match | **Needs Review** |

### Levetiracetam

| File | CMG | Title | Source Evidence | Status |
|------|-----|-------|----------------|--------|
| `CMG_22_Seizures.json` | 22 | Seizures | ICP drug list match | **Needs Review** |

### Lignocaine

| File | CMG | Title | Source Evidence | Status |
|------|-----|-------|----------------|--------|
| `CMG_8_Tachyarrhythmias.json` | 8 | Tachyarrhythmias | ICP drug list match | **Needs Review** |

### Sodium Bicarbonate

| File | CMG | Title | Source Evidence | Status |
|------|-----|-------|----------------|--------|
| `CMG_27_Hyperkalaemia.json` | 27 | Hyperkalaemia | ICP drug list match | **Needs Review** |
| `CMG_35A_Poisoning_and_Overdose.json` | 35A | Poisoning and Overdose | ICP drug list match | **Needs Review** |
| `CMG_4_Cardiac_Arrest__Adult.json` | 4 | Cardiac Arrest: Adult | ICP drug list match | **Needs Review** |
| `CMG_5_Cardiac_Arrest__Paediatric___12_years_old_.json` | 5 | Cardiac Arrest: Paediatric (<12 years old) | ICP drug list match | **Needs Review** |

### Suxamethonium

| File | CMG | Title | Source Evidence | Status |
|------|-----|-------|----------------|--------|
| `CMG_3A_RSI__Rapid_Sequence_Intubation_.json` | 3A | RSI (Rapid Sequence Intubation) | ICP drug list match | **Needs Review** |

---

## Summary Counts

| Category | Count |
|----------|-------|
| Files receiving `["ICP"]` at document level | 2 |
| Files receiving `["AP"]` at document level | 56 |
| ICP-tagged medicine–file pairs | 13 |
| Total files backfilled | 58 |

---

## How to Flag Errors

1. Change **Needs Review** → **Confirmed** once you have verified the entry is correct.
2. Change **Needs Review** → **ERROR: \<your correction\>** if the tagging is wrong.
3. Add any errors to `InfoERRORS.md` with an `InfoERROR` tag so the dev can re-run the
   backfill with updated rules.

---

## Re-running the Backfill After Corrections

```bash
# From repo root:
python scripts/backfill_actas_qualifications.py
```

The script is idempotent — it only writes files that need updating.
