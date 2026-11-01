# ACTAS AP/ICP Scope Tagging Review

**Date:** 2026-11-01
**Code:** `src/python/guidelines/actas_scope.py`. Regenerate the tables below with `python scripts/report_actas_scope.py`.
**Sources, in priority order:**
1. Oscar's medication, clinical skill and guideline scope lists (2026-11-01)
2. The ACTAS Clinical Management Guideline text itself: `**ICP:**`, `**- ICP only**`, `**AP:**`, `(ICP)` and `(ICP/AP)` labels
3. ACTAS Scope of Practice, POLACTAS001 Attachment A (reviewed 12/09/2024), for routes and indications of mixed-scope medicines. CSM.M07 Skills Matrix overrides the PDF for skills.

## How tagging works

- **Whole documents:** ICP-only medicines, ICP-only skills and CMG 3A/3B are ICP. Olanzapine is PACER only. The scraped `is_icp_only` flag is no longer trusted. It wrongly marked adrenaline, atropine, ketamine and magnesium as ICP-only, so AP users saw none of those monographs. It also missed adenosine, lignocaine, the AirTraq camera, BURP and cricothyroid pressure, so AP users saw all of those.
- **Mixed-scope medicine monographs:** an ICP label covers the labelled item and the unlabelled items directly under it (up to the next blank line or heading). An AP label resets that. Infusion, intubation and post-intubation sections are ICP. Explicit overrides (listed in the tables as "override") handle the cases the labels get wrong.
- **Guidelines and skills:** the ICP label covers only its own line, because ICP and AP steps are interleaved without blank lines. Lines and headings that name an ICP-only medicine are ICP.
- **Dose tables:** each row is tagged on its own. For mixed-scope medicines, rows that mention ETT, IO or infusion are ICP. Rows on an AP route from the scope PDF (for example adrenaline IM or nebulised, midazolam IM or SC) are shown to both. Rows whose route or indication can't be read are **kept ICP-only**. This hides some AP content rather than risk showing ICP content.
- **AP chunks are now built from the tagged text before splitting**, so an ICP block can't lose its label by being split across two chunks.

## What was wrong before

1. **ICP doses leaked into AP questions.** Unlabelled continuation lines of ICP blocks stayed in the AP text. For example, the adrenaline newborn ETT dose ("If no IV or IO access – 0.02mg/kg") and every adrenaline infusion pump limit were visible to AP users.
2. **Whole ICP-only medicines and skills were visible to AP users:** adenosine, lignocaine, the AirTraq camera, BURP and cricothyroid pressure.
3. **Several AP-scope monographs were hidden from AP users entirely:** adrenaline, atropine, ketamine and magnesium.
4. **Dose table tags were whole-medicine,** so every dose of a drug got the same tag whatever its route or indication.

## Oscar's decisions (2026-11-01)

1. **Atropine:** AP may give IM/IV/IO for organophosphate or nerve agent poisoning and big black spider bite with cholinergic symptoms. Bradyarrhythmia doses stay ICP.
2. **Morphine IV/IO** shared analgesia line shown to AP as written: confirmed.
3. **Palliative midazolam and morphine** (SC/IM/IV) shown to AP: confirmed.
4. **Adrenaline paediatric cardiac arrest:** AP may give IV, IO stays ICP. The calculator rows ("1:10,000 IV/IO 0.01mg/kg") are now shown to AP because the dose is the same. Rows that also carry the newborn ETT dose stay ICP. The adult "1mg IV or IO – fast push" row is shown to AP to match the monograph.
5. **CSM.DF08** shown to both: confirmed.
6. **CSM.A20 and A21** stay ICP.
7. **CSM.C07** is missing from the scraped data. A rescrape is added to Phase 0 of `docs/web-port-plan.md`.
8. **Misfiled doses fixed:** the ketamine "Up to 4mg/kg IM" dose is moved from midazolam to ketamine, and the fentanyl "1.5mcg/kg IN" dose is removed from naloxone. The fix is in `pipeline/actas/dose_tables.py` (`correct_misfiled_doses`), so a rescrape keeps it.

